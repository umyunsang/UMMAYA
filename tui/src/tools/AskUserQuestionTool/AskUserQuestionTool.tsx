import { feature } from 'bun:bundle'
import * as React from 'react'
import {
  getAllowedChannels,
  getQuestionPreviewFormat,
} from 'src/bootstrap/state.js'
import { MessageResponse } from 'src/components/MessageResponse.js'
import { BLACK_CIRCLE } from 'src/constants/figures.js'
import { getModeColor } from 'src/utils/permissions/PermissionMode.js'
import { z } from 'zod/v4'
import { Box, Text } from '../../ink.js'
import { buildTool, type Tool, type ToolDef } from '../../Tool.js'
import { lazySchema } from '../../utils/lazySchema.js'
import { buildAgentSupportMetadata } from '../AgentTool/orchestrationSupport.js'
import {
  ASK_USER_QUESTION_TOOL_CHIP_WIDTH,
  ASK_USER_QUESTION_TOOL_NAME,
  ASK_USER_QUESTION_TOOL_PROMPT,
  DESCRIPTION,
  PREVIEW_FEATURE_PROMPT,
} from './prompt.js'

const questionOptionSchema = lazySchema(() =>
  z.object({
    label: z.string().describe('The display text for this option that the user will see and select. Should be concise (1-5 words) and clearly describe the choice.'),
    description: z.string().describe('Explanation of what this option means or what will happen if chosen. Useful for providing context about trade-offs or implications.'),
    preview: z.string().optional().describe('Optional preview content rendered when this option is focused. Use for mockups, code snippets, or visual comparisons that help users compare options. See the tool description for the expected content format.'),
  }),
)

const questionSchema = lazySchema(() =>
  z.object({
    question: z.string().describe('The complete question to ask the user. Should be clear, specific, and end with a question mark.'),
    header: z.string().describe(`Very short label displayed as a chip/tag (max ${ASK_USER_QUESTION_TOOL_CHIP_WIDTH} chars).`),
    options: z.array(questionOptionSchema()).min(2).max(4).describe('The available choices for this question. Must have 2-4 options.'),
    multiSelect: z.boolean().default(false).describe('Set to true to allow the user to select multiple options instead of just one.'),
  }),
)

const annotationsSchema = lazySchema(() => {
  const annotationSchema = z.object({
    preview: z.string().optional().describe('The preview content of the selected option, if the question used previews.'),
    notes: z.string().optional().describe('Free-text notes the user added to their selection.'),
  })
  return z.record(z.string(), annotationSchema).optional()
})

const uniquenessRefine = {
  check: (data: { questions: { question: string; options: { label: string }[] }[] }) => {
    const questions = data.questions.map(q => q.question)
    if (questions.length !== new Set(questions).size) return false
    for (const question of data.questions) {
      const labels = question.options.map(option => option.label)
      if (labels.length !== new Set(labels).size) return false
    }
    return true
  },
  message:
    'Question texts must be unique, option labels must be unique within each question',
} as const

const commonFields = lazySchema(() => ({
  answers: z.record(z.string(), z.string()).optional(),
  annotations: annotationsSchema(),
  metadata: z.object({ source: z.string().optional() }).optional(),
}))

const inputSchema = lazySchema(() =>
  z
    .strictObject({
      questions: z.array(questionSchema()).min(1).max(4),
      ...commonFields(),
    })
    .refine(uniquenessRefine.check, { message: uniquenessRefine.message }),
)
type InputSchema = ReturnType<typeof inputSchema>

const outputSchema = lazySchema(() =>
  z.object({
    questions: z.array(questionSchema()),
    answers: z.record(z.string(), z.string()),
    annotations: annotationsSchema(),
    evidenceJoinKey: z.string(),
    parentToolUseId: z.string(),
    resumeToken: z.string(),
    permissionFlow: z.literal('coordinator_parent_round_trip'),
  }),
)
type OutputSchema = ReturnType<typeof outputSchema>

export const _sdkInputSchema = inputSchema
export const _sdkOutputSchema = outputSchema
export type Question = z.infer<ReturnType<typeof questionSchema>>
export type QuestionOption = z.infer<ReturnType<typeof questionOptionSchema>>
export type Output = z.infer<OutputSchema>

function AskUserQuestionResultMessage({
  answers,
}: {
  readonly answers: Output['answers']
}): React.ReactNode {
  return (
    <Box flexDirection="column" marginTop={1}>
      <Box flexDirection="row">
        <Text color={getModeColor('default')}>{BLACK_CIRCLE}&nbsp;</Text>
        <Text>User answered UMMAYA&apos;s questions:</Text>
      </Box>
      <MessageResponse>
        <Box flexDirection="column">
          {Object.entries(answers).map(([questionText, answer]) => (
            <Text key={questionText} color="inactive">
              · {questionText} → {answer}
            </Text>
          ))}
        </Box>
      </MessageResponse>
    </Box>
  )
}

function validateHtmlPreview(preview: string | undefined): string | null {
  if (preview === undefined) return null
  if (/<\s*(html|body|!doctype)\b/iu.test(preview)) {
    return 'preview must be an HTML fragment, not a full document (no <html>, <body>, or <!DOCTYPE>)'
  }
  if (/<\s*(script|style)\b/iu.test(preview)) {
    return 'preview must not contain <script> or <style> tags. Use inline styles via the style attribute if needed.'
  }
  if (!/<[a-z][^>]*>/iu.test(preview)) {
    return 'preview must contain HTML (previewFormat is set to "html"). Wrap content in a tag like <div> or <pre>.'
  }
  return null
}

export const AskUserQuestionTool: Tool<InputSchema, Output> = buildTool({
  name: ASK_USER_QUESTION_TOOL_NAME,
  searchHint: 'prompt the user with a multiple-choice question',
  maxResultSizeChars: 100_000,
  shouldDefer: true,
  async description() {
    return DESCRIPTION
  },
  async prompt() {
    const format = getQuestionPreviewFormat()
    return format === undefined
      ? ASK_USER_QUESTION_TOOL_PROMPT
      : ASK_USER_QUESTION_TOOL_PROMPT + PREVIEW_FEATURE_PROMPT[format]
  },
  get inputSchema(): InputSchema {
    return inputSchema()
  },
  get outputSchema(): OutputSchema {
    return outputSchema()
  },
  userFacingName() {
    return ''
  },
  isEnabled() {
    if ((feature('KAIROS') || feature('KAIROS_CHANNELS')) && getAllowedChannels().length > 0) {
      return false
    }
    return true
  },
  isConcurrencySafe() {
    return true
  },
  isReadOnly() {
    return true
  },
  toAutoClassifierInput(input) {
    return input.questions.map(question => question.question).join(' | ')
  },
  requiresUserInteraction() {
    return true
  },
  async validateInput({ questions }) {
    if (getQuestionPreviewFormat() !== 'html') return { result: true }
    for (const question of questions) {
      for (const option of question.options) {
        const error = validateHtmlPreview(option.preview)
        if (error) {
          return {
            result: false,
            message: `Option "${option.label}" in question "${question.question}": ${error}`,
            errorCode: 1,
          }
        }
      }
    }
    return { result: true }
  },
  async checkPermissions(input) {
    return { behavior: 'ask', message: 'Answer questions?', updatedInput: input }
  },
  renderToolUseMessage() {
    return null
  },
  renderToolUseProgressMessage() {
    return null
  },
  renderToolResultMessage({ answers }) {
    return <AskUserQuestionResultMessage answers={answers} />
  },
  renderToolUseRejectedMessage() {
    return (
      <Box flexDirection="row" marginTop={1}>
        <Text color={getModeColor('default')}>{BLACK_CIRCLE}&nbsp;</Text>
        <Text>User declined to answer questions</Text>
      </Box>
    )
  },
  renderToolUseErrorMessage() {
    return null
  },
  async call({ questions, answers = {}, annotations }, context) {
    return {
      data: {
        questions,
        answers,
        ...(annotations && { annotations }),
        ...buildAgentSupportMetadata({
          taskId: ASK_USER_QUESTION_TOOL_NAME,
          parentToolUseId: context.toolUseId,
        }),
      },
    }
  },
  mapToolResultToToolResultBlockParam(result, toolUseID) {
    const answersText = Object.entries(result.answers)
      .map(([questionText, answer]) => `"${questionText}"="${answer}"`)
      .join(', ')
    return {
      type: 'tool_result',
      content: `User has answered your questions: ${answersText}. You can now continue with the user's answers in mind.\n\nevidence_join_key: ${result.evidenceJoinKey}\nparent_tool_use_id: ${result.parentToolUseId}\nresume_token: ${result.resumeToken}\npermission_flow: ${result.permissionFlow}`,
      tool_use_id: toolUseID,
    }
  },
} satisfies ToolDef<InputSchema, Output>)
