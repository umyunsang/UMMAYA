import { execa } from 'execa';
import React, { useCallback, useState } from 'react';
import { type AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS, logEvent } from 'src/services/analytics/index.js';
import { WorkflowMultiselectDialog } from '../../components/WorkflowMultiselectDialog.js';
import { GITHUB_ACTION_SETUP_DOCS_URL } from '../../constants/github-app.js';
import { useExitOnCtrlCDWithKeybindings } from '../../hooks/useExitOnCtrlCDWithKeybindings.js';
import type { KeyboardEvent } from '../../ink/events/keyboard-event.js';
import { Box } from '../../ink.js';
import type { LocalJSXCommandOnDone } from '../../types/command.js';
import { FRIENDLI_PRIMARY_ENV, getAnthropicApiKey, isAnthropicAuthEnabled } from '../../utils/auth.js';
import { openBrowser } from '../../utils/browser.js';
import { execFileNoThrow } from '../../utils/execFileNoThrow.js';
import { getGithubRepo } from '../../utils/git.js';
import { plural } from '../../utils/stringUtils.js';
import { ApiKeyStep } from './ApiKeyStep.js';
import { CheckExistingSecretStep } from './CheckExistingSecretStep.js';
import { CheckGitHubStep } from './CheckGitHubStep.js';
import { ChooseRepoStep } from './ChooseRepoStep.js';
import { CreatingStep } from './CreatingStep.js';
import { ErrorStep } from './ErrorStep.js';
import { ExistingWorkflowStep } from './ExistingWorkflowStep.js';
import { InstallAppStep } from './InstallAppStep.js';
import { OAuthFlowStep } from './OAuthFlowStep.js';
import { SuccessStep } from './SuccessStep.js';
import { setupGitHubActions } from './setupGitHubActions.js';
import type { State, Warning, Workflow } from './types.js';
import { WarningsStep } from './WarningsStep.js';
const INITIAL_STATE: State = {
  step: 'check-gh',
  selectedRepoName: '',
  currentRepo: '',
  useCurrentRepo: false,
  // Default to false, will be set to true if repo detected
  apiKeyOrOAuthToken: '',
  useExistingKey: true,
  currentWorkflowInstallStep: 0,
  warnings: [],
  secretExists: false,
  secretName: FRIENDLI_PRIMARY_ENV,
  useExistingSecret: true,
  workflowExists: false,
  selectedWorkflows: ['ummaya', 'ummaya-review'] as Workflow[],
  selectedApiKeyOption: 'new' as 'existing' | 'new' | 'oauth',
  authType: 'api_key'
};
function secretListContains(lines: string[], secretName: string): boolean {
  const escapedSecretName = secretName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return lines.some((line: string) => new RegExp(`^${escapedSecretName}\\s+`).test(line));
}
function InstallGitHubApp(props: {
  onDone: (message: string) => void;
}): React.ReactNode {
  const [existingApiKey] = useState(() => getAnthropicApiKey());
  const [state, setState] = useState({
    ...INITIAL_STATE,
    useExistingKey: !!existingApiKey,
    selectedApiKeyOption: (existingApiKey ? 'existing' : isAnthropicAuthEnabled() ? 'oauth' : 'new') as 'existing' | 'new' | 'oauth'
  });
  useExitOnCtrlCDWithKeybindings();
  React.useEffect(() => {
    logEvent('tengu_install_github_app_started', {});
  }, []);
  const checkGitHubCLI = useCallback(async () => {
    const warnings: Warning[] = [];

    // Check if gh is installed
    const ghVersionResult = await execa('gh --version', {
      shell: true,
      reject: false
    });
    if (ghVersionResult.exitCode !== 0) {
      warnings.push({
        title: 'GitHub CLI not found',
        message: 'GitHub CLI (gh) does not appear to be installed or accessible.',
        instructions: ['Install GitHub CLI from https://cli.github.com/', 'macOS: brew install gh', 'Windows: winget install --id GitHub.cli', 'Linux: See installation instructions at https://github.com/cli/cli#installation']
      });
    }

    // Check auth status
    const authResult = await execa('gh auth status -a', {
      shell: true,
      reject: false
    });
    if (authResult.exitCode !== 0) {
      warnings.push({
        title: 'GitHub CLI not authenticated',
        message: 'GitHub CLI does not appear to be authenticated.',
        instructions: ['Run: gh auth login', 'Follow the prompts to authenticate with GitHub', 'Or set up authentication using environment variables or other methods']
      });
    } else {
      // Check if required scopes are present in the Token scopes line
      const tokenScopesMatch = authResult.stdout.match(/Token scopes:.*$/m);
      if (tokenScopesMatch) {
        const scopes = tokenScopesMatch[0];
        const missingScopes: string[] = [];
        if (!scopes.includes('repo')) {
          missingScopes.push('repo');
        }
        if (!scopes.includes('workflow')) {
          missingScopes.push('workflow');
        }
        if (missingScopes.length > 0) {
          // Missing required scopes - exit immediately
          setState(prev => ({
            ...prev,
            step: 'error',
            error: `GitHub CLI is missing required permissions: ${missingScopes.join(', ')}.`,
            errorReason: 'Missing required scopes',
            errorInstructions: [`Your GitHub CLI authentication is missing the "${missingScopes.join('" and "')}" ${plural(missingScopes.length, 'scope')} needed to manage GitHub Actions and secrets.`, '', 'To fix this, run:', '  gh auth refresh -h github.com -s repo,workflow', '', 'This will add the necessary permissions to manage workflows and secrets.']
          }));
          return;
        }
      }
    }

    // Check if in a git repo and get remote URL
    const currentRepo = (await getGithubRepo()) ?? '';
    logEvent('tengu_install_github_app_step_completed', {
      step: 'check-gh' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
    });
    setState(prev_0 => ({
      ...prev_0,
      warnings,
      currentRepo,
      selectedRepoName: currentRepo,
      useCurrentRepo: !!currentRepo,
      // Set to false if no repo detected
      step: warnings.length > 0 ? 'warnings' : 'choose-repo'
    }));
  }, []);
  React.useEffect(() => {
    if (state.step === 'check-gh') {
      void checkGitHubCLI();
    }
  }, [state.step, checkGitHubCLI]);
  const runSetupGitHubActions = useCallback(async (apiKeyOrOAuthToken: string | null, secretName: string) => {
    setState(prev_1 => ({
      ...prev_1,
      step: 'creating',
      currentWorkflowInstallStep: 0
    }));
    try {
      await setupGitHubActions(state.selectedRepoName, apiKeyOrOAuthToken, secretName, () => {
        setState(prev_4 => ({
          ...prev_4,
          currentWorkflowInstallStep: prev_4.currentWorkflowInstallStep + 1
        }));
      }, state.workflowAction === 'skip', state.selectedWorkflows, state.authType, {
        useCurrentRepo: state.useCurrentRepo,
        workflowExists: state.workflowExists,
        secretExists: state.secretExists
      });
      logEvent('tengu_install_github_app_step_completed', {
        step: 'creating' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
      });
      setState(prev_5 => ({
        ...prev_5,
        step: 'success'
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to set up GitHub Actions';
      if (errorMessage.includes('workflow file already exists')) {
        logEvent('tengu_install_github_app_error', {
          reason: 'workflow_file_exists' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
        });
        setState(prev_2 => ({
          ...prev_2,
          step: 'error',
          error: 'A UMMAYA workflow file already exists in this repository.',
          errorReason: 'Workflow file conflict',
          errorInstructions: ['The file .github/workflows/ummaya.yml already exists', 'You can either:', '  1. Delete the existing file and run this command again', '  2. Update the existing file manually using the template from:', `     ${GITHUB_ACTION_SETUP_DOCS_URL}`]
        }));
      } else {
        logEvent('tengu_install_github_app_error', {
          reason: 'setup_github_actions_failed' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
        });
        setState(prev_3 => ({
          ...prev_3,
          step: 'error',
          error: errorMessage,
          errorReason: 'GitHub Actions setup failed',
          errorInstructions: []
        }));
      }
    }
  }, [state.selectedRepoName, state.workflowAction, state.selectedWorkflows, state.useCurrentRepo, state.workflowExists, state.secretExists, state.authType]);
  async function openGitHubAppInstallation() {
    const installUrl = 'https://ummaya-docs.pages.dev/en/';
    await openBrowser(installUrl);
  }
  async function checkRepositoryPermissions(repoName: string): Promise<{
    hasAccess: boolean;
    error?: string;
  }> {
    try {
      const result = await execFileNoThrow('gh', ['api', `repos/${repoName}`, '--jq', '.permissions.admin']);
      if (result.code === 0) {
        const hasAdmin = result.stdout.trim() === 'true';
        return {
          hasAccess: hasAdmin
        };
      }
      if (result.stderr.includes('404') || result.stderr.includes('Not Found')) {
        return {
          hasAccess: false,
          error: 'repository_not_found'
        };
      }
      return {
        hasAccess: false
      };
    } catch {
      return {
        hasAccess: false
      };
    }
  }
  async function checkExistingWorkflowFile(repoName_0: string): Promise<boolean> {
    const checkFileResult = await execFileNoThrow('gh', ['api', `repos/${repoName_0}/contents/.github/workflows/ummaya.yml`, '--jq', '.sha']);
    return checkFileResult.code === 0;
  }
  async function checkExistingSecret() {
    const checkSecretsResult = await execFileNoThrow('gh', ['secret', 'list', '--app', 'actions', '--repo', state.selectedRepoName]);
    if (checkSecretsResult.code === 0) {
      const lines = checkSecretsResult.stdout.split('\n');
      const hasFriendliKey = secretListContains(lines, FRIENDLI_PRIMARY_ENV);
      if (hasFriendliKey) {
        setState(prev_6 => ({
          ...prev_6,
          secretExists: true,
          step: 'check-existing-secret'
        }));
      } else {
        // No existing secret found
        if (existingApiKey) {
          // User has local key, skip to creating with it
          setState(prev_7 => ({
            ...prev_7,
            apiKeyOrOAuthToken: existingApiKey,
            useExistingKey: true
          }));
          await runSetupGitHubActions(existingApiKey, state.secretName);
        } else {
          // No local key, go to API key step
          setState(prev_8 => ({
            ...prev_8,
            step: 'api-key'
          }));
        }
      }
    } else {
      // Error checking secrets
      if (existingApiKey) {
        // User has local key, skip to creating with it
        setState(prev_9 => ({
          ...prev_9,
          apiKeyOrOAuthToken: existingApiKey,
          useExistingKey: true
        }));
        await runSetupGitHubActions(existingApiKey, state.secretName);
      } else {
        // No local key, go to API key step
        setState(prev_10 => ({
          ...prev_10,
          step: 'api-key'
        }));
      }
    }
  }
  const handleSubmit = async () => {
    if (state.step === 'warnings') {
      logEvent('tengu_install_github_app_step_completed', {
        step: 'warnings' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
      });
      setState(prev_11 => ({
        ...prev_11,
        step: 'install-app'
      }));
      setTimeout(openGitHubAppInstallation, 0);
    } else if (state.step === 'choose-repo') {
      let repoName_1 = state.useCurrentRepo ? state.currentRepo : state.selectedRepoName;
      if (!repoName_1.trim()) {
        return;
      }
      const repoWarnings: Warning[] = [];
      if (repoName_1.includes('github.com')) {
        const match = repoName_1.match(/github\.com[:/]([^/]+\/[^/]+)(\.git)?$/);
        if (!match) {
          repoWarnings.push({
            title: 'Invalid GitHub URL format',
            message: 'The repository URL format appears to be invalid.',
            instructions: ['Use format: owner/repo or https://github.com/owner/repo', 'Example: umyunsang/UMMAYA']
          });
        } else {
          repoName_1 = match[1]?.replace(/\.git$/, '') || '';
        }
      }
      if (!repoName_1.includes('/')) {
        repoWarnings.push({
          title: 'Repository format warning',
          message: 'Repository should be in format "owner/repo"',
          instructions: ['Use format: owner/repo', 'Example: umyunsang/UMMAYA']
        });
      }
      const permissionCheck = await checkRepositoryPermissions(repoName_1);
      if (permissionCheck.error === 'repository_not_found') {
        repoWarnings.push({
          title: 'Repository not found',
          message: `Repository ${repoName_1} was not found or you don't have access.`,
          instructions: [`Check that the repository name is correct: ${repoName_1}`, 'Ensure you have access to this repository', 'For private repositories, make sure your GitHub token has the "repo" scope', 'You can add the repo scope with: gh auth refresh -h github.com -s repo,workflow']
        });
      } else if (!permissionCheck.hasAccess) {
        repoWarnings.push({
          title: 'Admin permissions required',
          message: `You might need admin permissions on ${repoName_1} to set up GitHub Actions.`,
          instructions: ['Repository admins can install GitHub Apps and set secrets', 'Ask a repository admin to run this command if setup fails', 'Alternatively, you can use the manual setup instructions']
        });
      }
      const workflowExists = await checkExistingWorkflowFile(repoName_1);
      if (repoWarnings.length > 0) {
        const allWarnings = [...state.warnings, ...repoWarnings];
        setState(prev_12 => ({
          ...prev_12,
          selectedRepoName: repoName_1,
          workflowExists,
          warnings: allWarnings,
          step: 'warnings'
        }));
      } else {
        logEvent('tengu_install_github_app_step_completed', {
          step: 'choose-repo' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
        });
        setState(prev_13 => ({
          ...prev_13,
          selectedRepoName: repoName_1,
          workflowExists,
          step: 'install-app'
        }));
        setTimeout(openGitHubAppInstallation, 0);
      }
    } else if (state.step === 'install-app') {
      logEvent('tengu_install_github_app_step_completed', {
        step: 'install-app' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
      });
      if (state.workflowExists) {
        setState(prev_14 => ({
          ...prev_14,
          step: 'check-existing-workflow'
        }));
      } else {
        setState(prev_15 => ({
          ...prev_15,
          step: 'select-workflows'
        }));
      }
    } else if (state.step === 'check-existing-workflow') {
      return;
    } else if (state.step === 'select-workflows') {
      // Handled by the WorkflowMultiselectDialog component
      return;
    } else if (state.step === 'check-existing-secret') {
      logEvent('tengu_install_github_app_step_completed', {
        step: 'check-existing-secret' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
      });
      if (state.useExistingSecret) {
        await runSetupGitHubActions(null, state.secretName);
      } else {
        // User wants to use a new secret name with their API key
        await runSetupGitHubActions(state.apiKeyOrOAuthToken, state.secretName);
      }
    } else if (state.step === 'api-key') {
      // In the new flow, api-key step only appears when user has no existing key
      // They either entered a new key or will create OAuth token
      if (state.selectedApiKeyOption === 'oauth') {
        // OAuth flow already handled by handleCreateOAuthToken
        return;
      }

      // If user selected 'existing' option, use the existing API key
      const apiKeyToUse = state.selectedApiKeyOption === 'existing' ? existingApiKey : state.apiKeyOrOAuthToken;
      if (!apiKeyToUse) {
        logEvent('tengu_install_github_app_error', {
          reason: 'api_key_missing' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
        });
        setState(prev_16 => ({
          ...prev_16,
          step: 'error',
          error: 'API key is required'
        }));
        return;
      }

      // Store the API key being used (either existing or newly entered)
      setState(prev_17 => ({
        ...prev_17,
        apiKeyOrOAuthToken: apiKeyToUse,
        useExistingKey: state.selectedApiKeyOption === 'existing'
      }));

      const checkSecretsResult_0 = await execFileNoThrow('gh', ['secret', 'list', '--app', 'actions', '--repo', state.selectedRepoName]);
      if (checkSecretsResult_0.code === 0) {
        const lines_0 = checkSecretsResult_0.stdout.split('\n');
        const hasFriendliKey_0 = secretListContains(lines_0, FRIENDLI_PRIMARY_ENV);
        if (hasFriendliKey_0) {
          logEvent('tengu_install_github_app_step_completed', {
            step: 'api-key' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
          });
          setState(prev_18 => ({
            ...prev_18,
            secretExists: true,
            step: 'check-existing-secret'
          }));
        } else {
          logEvent('tengu_install_github_app_step_completed', {
            step: 'api-key' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
          });
          // No existing secret, proceed to creating
          await runSetupGitHubActions(apiKeyToUse, state.secretName);
        }
      } else {
        logEvent('tengu_install_github_app_step_completed', {
          step: 'api-key' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
        });
        // Error checking secrets, proceed anyway
        await runSetupGitHubActions(apiKeyToUse, state.secretName);
      }
    }
  };
  const handleRepoUrlChange = (value: string) => {
    setState(prev_19 => ({
      ...prev_19,
      selectedRepoName: value
    }));
  };
  const handleApiKeyChange = (value_0: string) => {
    setState(prev_20 => ({
      ...prev_20,
      apiKeyOrOAuthToken: value_0
    }));
  };
  const handleApiKeyOptionChange = (option: 'existing' | 'new' | 'oauth') => {
    setState(prev_21 => ({
      ...prev_21,
      selectedApiKeyOption: option
    }));
  };
  const handleCreateOAuthToken = useCallback(() => {
    logEvent('tengu_install_github_app_step_completed', {
      step: 'api-key' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
    });
    setState(prev_22 => ({
      ...prev_22,
      step: 'oauth-flow'
    }));
  }, []);
  const handleOAuthSuccess = useCallback((token: string) => {
    logEvent('tengu_install_github_app_step_completed', {
      step: 'oauth-flow' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
    });
    setState(prev_23 => ({
      ...prev_23,
      apiKeyOrOAuthToken: token,
      useExistingKey: false,
      secretName: FRIENDLI_PRIMARY_ENV,
      authType: 'api_key'
    }));
    void runSetupGitHubActions(token, FRIENDLI_PRIMARY_ENV);
  }, [runSetupGitHubActions]);
  const handleOAuthCancel = useCallback(() => {
    setState(prev_24 => ({
      ...prev_24,
      step: 'api-key'
    }));
  }, []);
  const handleSecretNameChange = (value_1: string) => {
    if (value_1 && !/^[a-zA-Z0-9_]+$/.test(value_1)) return;
    setState(prev_25 => ({
      ...prev_25,
      secretName: value_1
    }));
  };
  const handleToggleUseCurrentRepo = (useCurrentRepo: boolean) => {
    setState(prev_26 => ({
      ...prev_26,
      useCurrentRepo,
      selectedRepoName: useCurrentRepo ? prev_26.currentRepo : ''
    }));
  };
  const handleToggleUseExistingKey = (useExistingKey: boolean) => {
    setState(prev_27 => ({
      ...prev_27,
      useExistingKey
    }));
  };
  const handleToggleUseExistingSecret = (useExistingSecret: boolean) => {
    setState(prev_28 => ({
      ...prev_28,
      useExistingSecret,
      secretName: useExistingSecret ? FRIENDLI_PRIMARY_ENV : ''
    }));
  };
  const handleWorkflowAction = async (action: 'update' | 'skip' | 'exit') => {
    if (action === 'exit') {
      props.onDone('Installation cancelled by user');
      return;
    }
    logEvent('tengu_install_github_app_step_completed', {
      step: 'check-existing-workflow' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
    });
    setState(prev_29 => ({
      ...prev_29,
      workflowAction: action
    }));
    if (action === 'skip' || action === 'update') {
      // Check if user has existing local API key
      if (existingApiKey) {
        await checkExistingSecret();
      } else {
        // No local key, go straight to API key step
        setState(prev_30 => ({
          ...prev_30,
          step: 'api-key'
        }));
      }
    }
  };
  function handleDismissKeyDown(e: KeyboardEvent): void {
    e.preventDefault();
    if (state.step === 'success') {
      logEvent('tengu_install_github_app_completed', {});
    }
    props.onDone(state.step === 'success' ? 'GitHub Actions setup complete!' : state.error ? `Couldn't install GitHub App: ${state.error}\nFor manual setup instructions, see: ${GITHUB_ACTION_SETUP_DOCS_URL}` : `GitHub App installation failed\nFor manual setup instructions, see: ${GITHUB_ACTION_SETUP_DOCS_URL}`);
  }
  switch (state.step) {
    case 'check-gh':
      return <CheckGitHubStep />;
    case 'warnings':
      return <WarningsStep warnings={state.warnings} onContinue={handleSubmit} />;
    case 'choose-repo':
      return <ChooseRepoStep currentRepo={state.currentRepo} useCurrentRepo={state.useCurrentRepo} repoUrl={state.selectedRepoName} onRepoUrlChange={handleRepoUrlChange} onToggleUseCurrentRepo={handleToggleUseCurrentRepo} onSubmit={handleSubmit} />;
    case 'install-app':
      return <InstallAppStep repoUrl={state.selectedRepoName} onSubmit={handleSubmit} />;
    case 'check-existing-workflow':
      return <ExistingWorkflowStep repoName={state.selectedRepoName} onSelectAction={handleWorkflowAction} />;
    case 'check-existing-secret':
      return <CheckExistingSecretStep useExistingSecret={state.useExistingSecret} secretName={state.secretName} onToggleUseExistingSecret={handleToggleUseExistingSecret} onSecretNameChange={handleSecretNameChange} onSubmit={handleSubmit} />;
    case 'api-key':
      return <ApiKeyStep existingApiKey={existingApiKey} useExistingKey={state.useExistingKey} apiKeyOrOAuthToken={state.apiKeyOrOAuthToken} onApiKeyChange={handleApiKeyChange} onToggleUseExistingKey={handleToggleUseExistingKey} onSubmit={handleSubmit} onCreateOAuthToken={isAnthropicAuthEnabled() ? handleCreateOAuthToken : undefined} selectedOption={state.selectedApiKeyOption} onSelectOption={handleApiKeyOptionChange} />;
    case 'creating':
      return <CreatingStep currentWorkflowInstallStep={state.currentWorkflowInstallStep} secretExists={state.secretExists} useExistingSecret={state.useExistingSecret} secretName={state.secretName} skipWorkflow={state.workflowAction === 'skip'} selectedWorkflows={state.selectedWorkflows} />;
    case 'success':
      return <Box tabIndex={0} autoFocus onKeyDown={handleDismissKeyDown}>
          <SuccessStep secretExists={state.secretExists} useExistingSecret={state.useExistingSecret} secretName={state.secretName} skipWorkflow={state.workflowAction === 'skip'} />
        </Box>;
    case 'error':
      return <Box tabIndex={0} autoFocus onKeyDown={handleDismissKeyDown}>
          <ErrorStep error={state.error} errorReason={state.errorReason} errorInstructions={state.errorInstructions} />
        </Box>;
    case 'select-workflows':
      return <WorkflowMultiselectDialog defaultSelections={state.selectedWorkflows} onSubmit={selectedWorkflows => {
        logEvent('tengu_install_github_app_step_completed', {
          step: 'select-workflows' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS
        });
        setState(prev_31 => ({
          ...prev_31,
          selectedWorkflows
        }));
        // Check if user has existing local API key
        if (existingApiKey) {
          void checkExistingSecret();
        } else {
          // No local key, go straight to API key step
          setState(prev_32 => ({
            ...prev_32,
            step: 'api-key'
          }));
        }
      }} />;
    case 'oauth-flow':
      return <OAuthFlowStep onSuccess={handleOAuthSuccess} onCancel={handleOAuthCancel} />;
  }
}
export async function call(onDone: LocalJSXCommandOnDone): Promise<React.ReactNode> {
  return <InstallGitHubApp onDone={onDone} />;
}
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJleGVjYSIsIlJlYWN0IiwidXNlQ2FsbGJhY2siLCJ1c2VTdGF0ZSIsIkFuYWx5dGljc01ldGFkYXRhX0lfVkVSSUZJRURfVEhJU19JU19OT1RfQ09ERV9PUl9GSUxFUEFUSFMiLCJsb2dFdmVudCIsIldvcmtmbG93TXVsdGlzZWxlY3REaWFsb2ciLCJHSVRIVUJfQUNUSU9OX1NFVFVQX0RPQ1NfVVJMIiwidXNlRXhpdE9uQ3RybENEV2l0aEtleWJpbmRpbmdzIiwiS2V5Ym9hcmRFdmVudCIsIkJveCIsIkxvY2FsSlNYQ29tbWFuZE9uRG9uZSIsImdldEFudGhyb3BpY0FwaUtleSIsImlzQW50aHJvcGljQXV0aEVuYWJsZWQiLCJvcGVuQnJvd3NlciIsImV4ZWNGaWxlTm9UaHJvdyIsImdldEdpdGh1YlJlcG8iLCJwbHVyYWwiLCJBcGlLZXlTdGVwIiwiQ2hlY2tFeGlzdGluZ1NlY3JldFN0ZXAiLCJDaGVja0dpdEh1YlN0ZXAiLCJDaG9vc2VSZXBvU3RlcCIsIkNyZWF0aW5nU3RlcCIsIkVycm9yU3RlcCIsIkV4aXN0aW5nV29ya2Zsb3dTdGVwIiwiSW5zdGFsbEFwcFN0ZXAiLCJPQXV0aEZsb3dTdGVwIiwiU3VjY2Vzc1N0ZXAiLCJzZXR1cEdpdEh1YkFjdGlvbnMiLCJTdGF0ZSIsIldhcm5pbmciLCJXb3JrZmxvdyIsIldhcm5pbmdzU3RlcCIsIklOSVRJQUxfU1RBVEUiLCJzdGVwIiwic2VsZWN0ZWRSZXBvTmFtZSIsImN1cnJlbnRSZXBvIiwidXNlQ3VycmVudFJlcG8iLCJhcGlLZXlPck9BdXRoVG9rZW4iLCJ1c2VFeGlzdGluZ0tleSIsImN1cnJlbnRXb3JrZmxvd0luc3RhbGxTdGVwIiwid2FybmluZ3MiLCJzZWNyZXRFeGlzdHMiLCJzZWNyZXROYW1lIiwidXNlRXhpc3RpbmdTZWNyZXQiLCJ3b3JrZmxvd0V4aXN0cyIsInNlbGVjdGVkV29ya2Zsb3dzIiwic2VsZWN0ZWRBcGlLZXlPcHRpb24iLCJhdXRoVHlwZSIsIkluc3RhbGxHaXRIdWJBcHAiLCJwcm9wcyIsIm9uRG9uZSIsIm1lc3NhZ2UiLCJSZWFjdE5vZGUiLCJleGlzdGluZ0FwaUtleSIsInN0YXRlIiwic2V0U3RhdGUiLCJ1c2VFZmZlY3QiLCJjaGVja0dpdEh1YkNMSSIsImdoVmVyc2lvblJlc3VsdCIsInNoZWxsIiwicmVqZWN0IiwiZXhpdENvZGUiLCJwdXNoIiwidGl0bGUiLCJpbnN0cnVjdGlvbnMiLCJhdXRoUmVzdWx0IiwidG9rZW5TY29wZXNNYXRjaCIsInN0ZG91dCIsIm1hdGNoIiwic2NvcGVzIiwibWlzc2luZ1Njb3BlcyIsImluY2x1ZGVzIiwibGVuZ3RoIiwicHJldiIsImVycm9yIiwiam9pbiIsImVycm9yUmVhc29uIiwiZXJyb3JJbnN0cnVjdGlvbnMiLCJydW5TZXR1cEdpdEh1YkFjdGlvbnMiLCJ3b3JrZmxvd0FjdGlvbiIsImVycm9yTWVzc2FnZSIsIkVycm9yIiwicmVhc29uIiwib3BlbkdpdEh1YkFwcEluc3RhbGxhdGlvbiIsImluc3RhbGxVcmwiLCJjaGVja1JlcG9zaXRvcnlQZXJtaXNzaW9ucyIsInJlcG9OYW1lIiwiUHJvbWlzZSIsImhhc0FjY2VzcyIsInJlc3VsdCIsImNvZGUiLCJoYXNBZG1pbiIsInRyaW0iLCJzdGRlcnIiLCJjaGVja0V4aXN0aW5nV29ya2Zsb3dGaWxlIiwiY2hlY2tGaWxlUmVzdWx0IiwiY2hlY2tFeGlzdGluZ1NlY3JldCIsImNoZWNrU2VjcmV0c1Jlc3VsdCIsImxpbmVzIiwic3BsaXQiLCJoYXNBbnRocm9waWNLZXkiLCJzb21lIiwibGluZSIsInRlc3QiLCJoYW5kbGVTdWJtaXQiLCJzZXRUaW1lb3V0IiwicmVwb1dhcm5pbmdzIiwicmVwbGFjZSIsInBlcm1pc3Npb25DaGVjayIsImFsbFdhcm5pbmdzIiwiYXBpS2V5VG9Vc2UiLCJoYW5kbGVSZXBvVXJsQ2hhbmdlIiwidmFsdWUiLCJoYW5kbGVBcGlLZXlDaGFuZ2UiLCJoYW5kbGVBcGlLZXlPcHRpb25DaGFuZ2UiLCJvcHRpb24iLCJoYW5kbGVDcmVhdGVPQXV0aFRva2VuIiwiaGFuZGxlT0F1dGhTdWNjZXNzIiwidG9rZW4iLCJoYW5kbGVPQXV0aENhbmNlbCIsImhhbmRsZVNlY3JldE5hbWVDaGFuZ2UiLCJoYW5kbGVUb2dnbGVVc2VDdXJyZW50UmVwbyIsImhhbmRsZVRvZ2dsZVVzZUV4aXN0aW5nS2V5IiwiaGFuZGxlVG9nZ2xlVXNlRXhpc3RpbmdTZWNyZXQiLCJoYW5kbGVXb3JrZmxvd0FjdGlvbiIsImFjdGlvbiIsImhhbmRsZURpc21pc3NLZXlEb3duIiwiZSIsInByZXZlbnREZWZhdWx0IiwidW5kZWZpbmVkIiwiY2FsbCJdLCJzb3VyY2VzIjpbImluc3RhbGwtZ2l0aHViLWFwcC50c3giXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZXhlY2EgfSBmcm9tICdleGVjYSdcbmltcG9ydCBSZWFjdCwgeyB1c2VDYWxsYmFjaywgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCdcbmltcG9ydCB7XG4gIHR5cGUgQW5hbHl0aWNzTWV0YWRhdGFfSV9WRVJJRklFRF9USElTX0lTX05PVF9DT0RFX09SX0ZJTEVQQVRIUyxcbiAgbG9nRXZlbnQsXG59IGZyb20gJ3NyYy9zZXJ2aWNlcy9hbmFseXRpY3MvaW5kZXguanMnXG5pbXBvcnQgeyBXb3JrZmxvd011bHRpc2VsZWN0RGlhbG9nIH0gZnJvbSAnLi4vLi4vY29tcG9uZW50cy9Xb3JrZmxvd011bHRpc2VsZWN0RGlhbG9nLmpzJ1xuaW1wb3J0IHsgR0lUSFVCX0FDVElPTl9TRVRVUF9ET0NTX1VSTCB9IGZyb20gJy4uLy4uL2NvbnN0YW50cy9naXRodWItYXBwLmpzJ1xuaW1wb3J0IHsgdXNlRXhpdE9uQ3RybENEV2l0aEtleWJpbmRpbmdzIH0gZnJvbSAnLi4vLi4vaG9va3MvdXNlRXhpdE9uQ3RybENEV2l0aEtleWJpbmRpbmdzLmpzJ1xuaW1wb3J0IHR5cGUgeyBLZXlib2FyZEV2ZW50IH0gZnJvbSAnLi4vLi4vaW5rL2V2ZW50cy9rZXlib2FyZC1ldmVudC5qcydcbmltcG9ydCB7IEJveCB9IGZyb20gJy4uLy4uL2luay5qcydcbmltcG9ydCB0eXBlIHsgTG9jYWxKU1hDb21tYW5kT25Eb25lIH0gZnJvbSAnLi4vLi4vdHlwZXMvY29tbWFuZC5qcydcbmltcG9ydCB7IGdldEFudGhyb3BpY0FwaUtleSwgaXNBbnRocm9waWNBdXRoRW5hYmxlZCB9IGZyb20gJy4uLy4uL3V0aWxzL2F1dGguanMnXG5pbXBvcnQgeyBvcGVuQnJvd3NlciB9IGZyb20gJy4uLy4uL3V0aWxzL2Jyb3dzZXIuanMnXG5pbXBvcnQgeyBleGVjRmlsZU5vVGhyb3cgfSBmcm9tICcuLi8uLi91dGlscy9leGVjRmlsZU5vVGhyb3cuanMnXG5pbXBvcnQgeyBnZXRHaXRodWJSZXBvIH0gZnJvbSAnLi4vLi4vdXRpbHMvZ2l0LmpzJ1xuaW1wb3J0IHsgcGx1cmFsIH0gZnJvbSAnLi4vLi4vdXRpbHMvc3RyaW5nVXRpbHMuanMnXG5pbXBvcnQgeyBBcGlLZXlTdGVwIH0gZnJvbSAnLi9BcGlLZXlTdGVwLmpzJ1xuaW1wb3J0IHsgQ2hlY2tFeGlzdGluZ1NlY3JldFN0ZXAgfSBmcm9tICcuL0NoZWNrRXhpc3RpbmdTZWNyZXRTdGVwLmpzJ1xuaW1wb3J0IHsgQ2hlY2tHaXRIdWJTdGVwIH0gZnJvbSAnLi9DaGVja0dpdEh1YlN0ZXAuanMnXG5pbXBvcnQgeyBDaG9vc2VSZXBvU3RlcCB9IGZyb20gJy4vQ2hvb3NlUmVwb1N0ZXAuanMnXG5pbXBvcnQgeyBDcmVhdGluZ1N0ZXAgfSBmcm9tICcuL0NyZWF0aW5nU3RlcC5qcydcbmltcG9ydCB7IEVycm9yU3RlcCB9IGZyb20gJy4vRXJyb3JTdGVwLmpzJ1xuaW1wb3J0IHsgRXhpc3RpbmdXb3JrZmxvd1N0ZXAgfSBmcm9tICcuL0V4aXN0aW5nV29ya2Zsb3dTdGVwLmpzJ1xuaW1wb3J0IHsgSW5zdGFsbEFwcFN0ZXAgfSBmcm9tICcuL0luc3RhbGxBcHBTdGVwLmpzJ1xuaW1wb3J0IHsgT0F1dGhGbG93U3RlcCB9IGZyb20gJy4vT0F1dGhGbG93U3RlcC5qcydcbmltcG9ydCB7IFN1Y2Nlc3NTdGVwIH0gZnJvbSAnLi9TdWNjZXNzU3RlcC5qcydcbmltcG9ydCB7IHNldHVwR2l0SHViQWN0aW9ucyB9IGZyb20gJy4vc2V0dXBHaXRIdWJBY3Rpb25zLmpzJ1xuaW1wb3J0IHR5cGUgeyBTdGF0ZSwgV2FybmluZywgV29ya2Zsb3cgfSBmcm9tICcuL3R5cGVzLmpzJ1xuaW1wb3J0IHsgV2FybmluZ3NTdGVwIH0gZnJvbSAnLi9XYXJuaW5nc1N0ZXAuanMnXG5cbmNvbnN0IElOSVRJQUxfU1RBVEU6IFN0YXRlID0ge1xuICBzdGVwOiAnY2hlY2stZ2gnLFxuICBzZWxlY3RlZFJlcG9OYW1lOiAnJyxcbiAgY3VycmVudFJlcG86ICcnLFxuICB1c2VDdXJyZW50UmVwbzogZmFsc2UsIC8vIERlZmF1bHQgdG8gZmFsc2UsIHdpbGwgYmUgc2V0IHRvIHRydWUgaWYgcmVwbyBkZXRlY3RlZFxuICBhcGlLZXlPck9BdXRoVG9rZW46ICcnLFxuICB1c2VFeGlzdGluZ0tleTogdHJ1ZSxcbiAgY3VycmVudFdvcmtmbG93SW5zdGFsbFN0ZXA6IDAsXG4gIHdhcm5pbmdzOiBbXSxcbiAgc2VjcmV0RXhpc3RzOiBmYWxzZSxcbiAgc2VjcmV0TmFtZTogRlJJRU5ETElfUFJJTUFSWV9FTlYsXG4gIHVzZUV4aXN0aW5nU2VjcmV0OiB0cnVlLFxuICB3b3JrZmxvd0V4aXN0czogZmFsc2UsXG4gIHNlbGVjdGVkV29ya2Zsb3dzOiBbJ3VtbWF5YScsICd1bW1heWEtcmV2aWV3J10gYXMgV29ya2Zsb3dbXSxcbiAgc2VsZWN0ZWRBcGlLZXlPcHRpb246ICduZXcnIGFzICdleGlzdGluZycgfCAnbmV3JyB8ICdvYXV0aCcsXG4gIGF1dGhUeXBlOiAnYXBpX2tleScsXG59XG5cbmZ1bmN0aW9uIEluc3RhbGxHaXRIdWJBcHAocHJvcHM6IHtcbiAgb25Eb25lOiAobWVzc2FnZTogc3RyaW5nKSA9PiB2b2lkXG59KTogUmVhY3QuUmVhY3ROb2RlIHtcbiAgY29uc3QgW2V4aXN0aW5nQXBpS2V5XSA9IHVzZVN0YXRlKCgpID0+IGdldEFudGhyb3BpY0FwaUtleSgpKVxuICBjb25zdCBbc3RhdGUsIHNldFN0YXRlXSA9IHVzZVN0YXRlKHtcbiAgICAuLi5JTklUSUFMX1NUQVRFLFxuICAgIHVzZUV4aXN0aW5nS2V5OiAhIWV4aXN0aW5nQXBpS2V5LFxuICAgIHNlbGVjdGVkQXBpS2V5T3B0aW9uOiAoZXhpc3RpbmdBcGlLZXlcbiAgICAgID8gJ2V4aXN0aW5nJ1xuICAgICAgOiBpc0FudGhyb3BpY0F1dGhFbmFibGVkKClcbiAgICAgICAgPyAnb2F1dGgnXG4gICAgICAgIDogJ25ldycpIGFzICdleGlzdGluZycgfCAnbmV3JyB8ICdvYXV0aCcsXG4gIH0pXG4gIHVzZUV4aXRPbkN0cmxDRFdpdGhLZXliaW5kaW5ncygpXG5cbiAgUmVhY3QudXNlRWZmZWN0KCgpID0+IHtcbiAgICBsb2dFdmVudCgndGVuZ3VfaW5zdGFsbF9naXRodWJfYXBwX3N0YXJ0ZWQnLCB7fSlcbiAgfSwgW10pXG5cbiAgY29uc3QgY2hlY2tHaXRIdWJDTEkgPSB1c2VDYWxsYmFjayhhc3luYyAoKSA9PiB7XG4gICAgY29uc3Qgd2FybmluZ3M6IFdhcm5pbmdbXSA9IFtdXG5cbiAgICAvLyBDaGVjayBpZiBnaCBpcyBpbnN0YWxsZWRcbiAgICBjb25zdCBnaFZlcnNpb25SZXN1bHQgPSBhd2FpdCBleGVjYSgnZ2ggLS12ZXJzaW9uJywge1xuICAgICAgc2hlbGw6IHRydWUsXG4gICAgICByZWplY3Q6IGZhbHNlLFxuICAgIH0pXG4gICAgaWYgKGdoVmVyc2lvblJlc3VsdC5leGl0Q29kZSAhPT0gMCkge1xuICAgICAgd2FybmluZ3MucHVzaCh7XG4gICAgICAgIHRpdGxlOiAnR2l0SHViIENMSSBub3QgZm91bmQnLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICdHaXRIdWIgQ0xJIChnaCkgZG9lcyBub3QgYXBwZWFyIHRvIGJlIGluc3RhbGxlZCBvciBhY2Nlc3NpYmxlLicsXG4gICAgICAgIGluc3RydWN0aW9uczogW1xuICAgICAgICAgICdJbnN0YWxsIEdpdEh1YiBDTEkgZnJvbSBodHRwczovL2NsaS5naXRodWIuY29tLycsXG4gICAgICAgICAgJ21hY09TOiBicmV3IGluc3RhbGwgZ2gnLFxuICAgICAgICAgICdXaW5kb3dzOiB3aW5nZXQgaW5zdGFsbCAtLWlkIEdpdEh1Yi5jbGknLFxuICAgICAgICAgICdMaW51eDogU2VlIGluc3RhbGxhdGlvbiBpbnN0cnVjdGlvbnMgYXQgaHR0cHM6Ly9naXRodWIuY29tL2NsaS9jbGkjaW5zdGFsbGF0aW9uJyxcbiAgICAgICAgXSxcbiAgICAgIH0pXG4gICAgfVxuXG4gICAgLy8gQ2hlY2sgYXV0aCBzdGF0dXNcbiAgICBjb25zdCBhdXRoUmVzdWx0ID0gYXdhaXQgZXhlY2EoJ2doIGF1dGggc3RhdHVzIC1hJywge1xuICAgICAgc2hlbGw6IHRydWUsXG4gICAgICByZWplY3Q6IGZhbHNlLFxuICAgIH0pXG4gICAgaWYgKGF1dGhSZXN1bHQuZXhpdENvZGUgIT09IDApIHtcbiAgICAgIHdhcm5pbmdzLnB1c2goe1xuICAgICAgICB0aXRsZTogJ0dpdEh1YiBDTEkgbm90IGF1dGhlbnRpY2F0ZWQnLFxuICAgICAgICBtZXNzYWdlOiAnR2l0SHViIENMSSBkb2VzIG5vdCBhcHBlYXIgdG8gYmUgYXV0aGVudGljYXRlZC4nLFxuICAgICAgICBpbnN0cnVjdGlvbnM6IFtcbiAgICAgICAgICAnUnVuOiBnaCBhdXRoIGxvZ2luJyxcbiAgICAgICAgICAnRm9sbG93IHRoZSBwcm9tcHRzIHRvIGF1dGhlbnRpY2F0ZSB3aXRoIEdpdEh1YicsXG4gICAgICAgICAgJ09yIHNldCB1cCBhdXRoZW50aWNhdGlvbiB1c2luZyBlbnZpcm9ubWVudCB2YXJpYWJsZXMgb3Igb3RoZXIgbWV0aG9kcycsXG4gICAgICAgIF0sXG4gICAgICB9KVxuICAgIH0gZWxzZSB7XG4gICAgICAvLyBDaGVjayBpZiByZXF1aXJlZCBzY29wZXMgYXJlIHByZXNlbnQgaW4gdGhlIFRva2VuIHNjb3BlcyBsaW5lXG4gICAgICBjb25zdCB0b2tlblNjb3Blc01hdGNoID0gYXV0aFJlc3VsdC5zdGRvdXQubWF0Y2goL1Rva2VuIHNjb3BlczouKiQvbSlcbiAgICAgIGlmICh0b2tlblNjb3Blc01hdGNoKSB7XG4gICAgICAgIGNvbnN0IHNjb3BlcyA9IHRva2VuU2NvcGVzTWF0Y2hbMF1cbiAgICAgICAgY29uc3QgbWlzc2luZ1Njb3Blczogc3RyaW5nW10gPSBbXVxuXG4gICAgICAgIGlmICghc2NvcGVzLmluY2x1ZGVzKCdyZXBvJykpIHtcbiAgICAgICAgICBtaXNzaW5nU2NvcGVzLnB1c2goJ3JlcG8nKVxuICAgICAgICB9XG4gICAgICAgIGlmICghc2NvcGVzLmluY2x1ZGVzKCd3b3JrZmxvdycpKSB7XG4gICAgICAgICAgbWlzc2luZ1Njb3Blcy5wdXNoKCd3b3JrZmxvdycpXG4gICAgICAgIH1cblxuICAgICAgICBpZiAobWlzc2luZ1Njb3Blcy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgLy8gTWlzc2luZyByZXF1aXJlZCBzY29wZXMgLSBleGl0IGltbWVkaWF0ZWx5XG4gICAgICAgICAgc2V0U3RhdGUocHJldiA9PiAoe1xuICAgICAgICAgICAgLi4ucHJldixcbiAgICAgICAgICAgIHN0ZXA6ICdlcnJvcicsXG4gICAgICAgICAgICBlcnJvcjogYEdpdEh1YiBDTEkgaXMgbWlzc2luZyByZXF1aXJlZCBwZXJtaXNzaW9uczogJHttaXNzaW5nU2NvcGVzLmpvaW4oJywgJyl9LmAsXG4gICAgICAgICAgICBlcnJvclJlYXNvbjogJ01pc3NpbmcgcmVxdWlyZWQgc2NvcGVzJyxcbiAgICAgICAgICAgIGVycm9ySW5zdHJ1Y3Rpb25zOiBbXG4gICAgICAgICAgICAgIGBZb3VyIEdpdEh1YiBDTEkgYXV0aGVudGljYXRpb24gaXMgbWlzc2luZyB0aGUgXCIke21pc3NpbmdTY29wZXMuam9pbignXCIgYW5kIFwiJyl9XCIgJHtwbHVyYWwobWlzc2luZ1Njb3Blcy5sZW5ndGgsICdzY29wZScpfSBuZWVkZWQgdG8gbWFuYWdlIEdpdEh1YiBBY3Rpb25zIGFuZCBzZWNyZXRzLmAsXG4gICAgICAgICAgICAgICcnLFxuICAgICAgICAgICAgICAnVG8gZml4IHRoaXMsIHJ1bjonLFxuICAgICAgICAgICAgICAnICBnaCBhdXRoIHJlZnJlc2ggLWggZ2l0aHViLmNvbSAtcyByZXBvLHdvcmtmbG93JyxcbiAgICAgICAgICAgICAgJycsXG4gICAgICAgICAgICAgICdUaGlzIHdpbGwgYWRkIHRoZSBuZWNlc3NhcnkgcGVybWlzc2lvbnMgdG8gbWFuYWdlIHdvcmtmbG93cyBhbmQgc2VjcmV0cy4nLFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9KSlcbiAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIC8vIENoZWNrIGlmIGluIGEgZ2l0IHJlcG8gYW5kIGdldCByZW1vdGUgVVJMXG4gICAgY29uc3QgY3VycmVudFJlcG8gPSAoYXdhaXQgZ2V0R2l0aHViUmVwbygpKSA/PyAnJ1xuXG4gICAgbG9nRXZlbnQoJ3Rlbmd1X2luc3RhbGxfZ2l0aHViX2FwcF9zdGVwX2NvbXBsZXRlZCcsIHtcbiAgICAgIHN0ZXA6ICdjaGVjay1naCcgYXMgQW5hbHl0aWNzTWV0YWRhdGFfSV9WRVJJRklFRF9USElTX0lTX05PVF9DT0RFX09SX0ZJTEVQQVRIUyxcbiAgICB9KVxuXG4gICAgc2V0U3RhdGUocHJldiA9PiAoe1xuICAgICAgLi4ucHJldixcbiAgICAgIHdhcm5pbmdzLFxuICAgICAgY3VycmVudFJlcG8sXG4gICAgICBzZWxlY3RlZFJlcG9OYW1lOiBjdXJyZW50UmVwbyxcbiAgICAgIHVzZUN1cnJlbnRSZXBvOiAhIWN1cnJlbnRSZXBvLCAvLyBTZXQgdG8gZmFsc2UgaWYgbm8gcmVwbyBkZXRlY3RlZFxuICAgICAgc3RlcDogd2FybmluZ3MubGVuZ3RoID4gMCA/ICd3YXJuaW5ncycgOiAnY2hvb3NlLXJlcG8nLFxuICAgIH0pKVxuICB9LCBbXSlcblxuICBSZWFjdC51c2VFZmZlY3QoKCkgPT4ge1xuICAgIGlmIChzdGF0ZS5zdGVwID09PSAnY2hlY2stZ2gnKSB7XG4gICAgICB2b2lkIGNoZWNrR2l0SHViQ0xJKClcbiAgICB9XG4gIH0sIFtzdGF0ZS5zdGVwLCBjaGVja0dpdEh1YkNMSV0pXG5cbiAgY29uc3QgcnVuU2V0dXBHaXRIdWJBY3Rpb25zID0gdXNlQ2FsbGJhY2soXG4gICAgYXN5bmMgKGFwaUtleU9yT0F1dGhUb2tlbjogc3RyaW5nIHwgbnVsbCwgc2VjcmV0TmFtZTogc3RyaW5nKSA9PiB7XG4gICAgICBzZXRTdGF0ZShwcmV2ID0+ICh7XG4gICAgICAgIC4uLnByZXYsXG4gICAgICAgIHN0ZXA6ICdjcmVhdGluZycsXG4gICAgICAgIGN1cnJlbnRXb3JrZmxvd0luc3RhbGxTdGVwOiAwLFxuICAgICAgfSkpXG5cbiAgICAgIHRyeSB7XG4gICAgICAgIGF3YWl0IHNldHVwR2l0SHViQWN0aW9ucyhcbiAgICAgICAgICBzdGF0ZS5zZWxlY3RlZFJlcG9OYW1lLFxuICAgICAgICAgIGFwaUtleU9yT0F1dGhUb2tlbixcbiAgICAgICAgICBzZWNyZXROYW1lLFxuICAgICAgICAgICgpID0+IHtcbiAgICAgICAgICAgIHNldFN0YXRlKHByZXYgPT4gKHtcbiAgICAgICAgICAgICAgLi4ucHJldixcbiAgICAgICAgICAgICAgY3VycmVudFdvcmtmbG93SW5zdGFsbFN0ZXA6IHByZXYuY3VycmVudFdvcmtmbG93SW5zdGFsbFN0ZXAgKyAxLFxuICAgICAgICAgICAgfSkpXG4gICAgICAgICAgfSxcbiAgICAgICAgICBzdGF0ZS53b3JrZmxvd0FjdGlvbiA9PT0gJ3NraXAnLFxuICAgICAgICAgIHN0YXRlLnNlbGVjdGVkV29ya2Zsb3dzLFxuICAgICAgICAgIHN0YXRlLmF1dGhUeXBlLFxuICAgICAgICAgIHtcbiAgICAgICAgICAgIHVzZUN1cnJlbnRSZXBvOiBzdGF0ZS51c2VDdXJyZW50UmVwbyxcbiAgICAgICAgICAgIHdvcmtmbG93RXhpc3RzOiBzdGF0ZS53b3JrZmxvd0V4aXN0cyxcbiAgICAgICAgICAgIHNlY3JldEV4aXN0czogc3RhdGUuc2VjcmV0RXhpc3RzLFxuICAgICAgICAgIH0sXG4gICAgICAgIClcbiAgICAgICAgbG9nRXZlbnQoJ3Rlbmd1X2luc3RhbGxfZ2l0aHViX2FwcF9zdGVwX2NvbXBsZXRlZCcsIHtcbiAgICAgICAgICBzdGVwOiAnY3JlYXRpbmcnIGFzIEFuYWx5dGljc01ldGFkYXRhX0lfVkVSSUZJRURfVEhJU19JU19OT1RfQ09ERV9PUl9GSUxFUEFUSFMsXG4gICAgICAgIH0pXG4gICAgICAgIHNldFN0YXRlKHByZXYgPT4gKHsgLi4ucHJldiwgc3RlcDogJ3N1Y2Nlc3MnIH0pKVxuICAgICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgICAgY29uc3QgZXJyb3JNZXNzYWdlID1cbiAgICAgICAgICBlcnJvciBpbnN0YW5jZW9mIEVycm9yXG4gICAgICAgICAgICA/IGVycm9yLm1lc3NhZ2VcbiAgICAgICAgICAgIDogJ0ZhaWxlZCB0byBzZXQgdXAgR2l0SHViIEFjdGlvbnMnXG5cbiAgICAgICAgaWYgKGVycm9yTWVzc2FnZS5pbmNsdWRlcygnd29ya2Zsb3cgZmlsZSBhbHJlYWR5IGV4aXN0cycpKSB7XG4gICAgICAgICAgbG9nRXZlbnQoJ3Rlbmd1X2luc3RhbGxfZ2l0aHViX2FwcF9lcnJvcicsIHtcbiAgICAgICAgICAgIHJlYXNvbjpcbiAgICAgICAgICAgICAgJ3dvcmtmbG93X2ZpbGVfZXhpc3RzJyBhcyBBbmFseXRpY3NNZXRhZGF0YV9JX1ZFUklGSUVEX1RISVNfSVNfTk9UX0NPREVfT1JfRklMRVBBVEhTLFxuICAgICAgICAgIH0pXG4gICAgICAgICAgc2V0U3RhdGUocHJldiA9PiAoe1xuICAgICAgICAgICAgLi4ucHJldixcbiAgICAgICAgICAgIHN0ZXA6ICdlcnJvcicsXG4gICAgICAgICAgICBlcnJvcjogJ0EgQ2xhdWRlIHdvcmtmbG93IGZpbGUgYWxyZWFkeSBleGlzdHMgaW4gdGhpcyByZXBvc2l0b3J5LicsXG4gICAgICAgICAgICBlcnJvclJlYXNvbjogJ1dvcmtmbG93IGZpbGUgY29uZmxpY3QnLFxuICAgICAgICAgICAgZXJyb3JJbnN0cnVjdGlvbnM6IFtcbiAgICAgICAgICAgICAgJ1RoZSBmaWxlIC5naXRodWIvd29ya2Zsb3dzL3VtbWF5YS55bWwgYWxyZWFkeSBleGlzdHMnLFxuICAgICAgICAgICAgICAnWW91IGNhbiBlaXRoZXI6JyxcbiAgICAgICAgICAgICAgJyAgMS4gRGVsZXRlIHRoZSBleGlzdGluZyBmaWxlIGFuZCBydW4gdGhpcyBjb21tYW5kIGFnYWluJyxcbiAgICAgICAgICAgICAgJyAgMi4gVXBkYXRlIHRoZSBleGlzdGluZyBmaWxlIG1hbnVhbGx5IHVzaW5nIHRoZSB0ZW1wbGF0ZSBmcm9tOicsXG4gICAgICAgICAgICAgIGAgICAgICR7R0lUSFVCX0FDVElPTl9TRVRVUF9ET0NTX1VSTH1gLFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9KSlcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBsb2dFdmVudCgndGVuZ3VfaW5zdGFsbF9naXRodWJfYXBwX2Vycm9yJywge1xuICAgICAgICAgICAgcmVhc29uOlxuICAgICAgICAgICAgICAnc2V0dXBfZ2l0aHViX2FjdGlvbnNfZmFpbGVkJyBhcyBBbmFseXRpY3NNZXRhZGF0YV9JX1ZFUklGSUVEX1RISVNfSVNfTk9UX0NPREVfT1JfRklMRVBBVEhTLFxuICAgICAgICAgIH0pXG5cbiAgICAgICAgICBzZXRTdGF0ZShwcmV2ID0+ICh7XG4gICAgICAgICAgICAuLi5wcmV2LFxuICAgICAgICAgICAgc3RlcDogJ2Vycm9yJyxcbiAgICAgICAgICAgIGVycm9yOiBlcnJvck1lc3NhZ2UsXG4gICAgICAgICAgICBlcnJvclJlYXNvbjogJ0dpdEh1YiBBY3Rpb25zIHNldHVwIGZhaWxlZCcsXG4gICAgICAgICAgICBlcnJvckluc3RydWN0aW9uczogW10sXG4gICAgICAgICAgfSkpXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9LFxuICAgIFtcbiAgICAgIHN0YXRlLnNlbGVjdGVkUmVwb05hbWUsXG4gICAgICBzdGF0ZS53b3JrZmxvd0FjdGlvbixcbiAgICAgIHN0YXRlLnNlbGVjdGVkV29ya2Zsb3dzLFxuICAgICAgc3RhdGUudXNlQ3VycmVudFJlcG8sXG4gICAgICBzdGF0ZS53b3JrZmxvd0V4aXN0cyxcbiAgICAgIHN0YXRlLnNlY3JldEV4aXN0cyxcbiAgICAgIHN0YXRlLmF1dGhUeXBlLFxuICAgIF0sXG4gIClcblxuICBhc3luYyBmdW5jdGlvbiBvcGVuR2l0SHViQXBwSW5zdGFsbGF0aW9uKCkge1xuICAgIGNvbnN0IGluc3RhbGxVcmwgPSAnaHR0cHM6Ly9naXRodWIuY29tL2FwcHMvY2xhdWRlJ1xuICAgIGF3YWl0IG9wZW5Ccm93c2VyKGluc3RhbGxVcmwpXG4gIH1cblxuICBhc3luYyBmdW5jdGlvbiBjaGVja1JlcG9zaXRvcnlQZXJtaXNzaW9ucyhcbiAgICByZXBvTmFtZTogc3RyaW5nLFxuICApOiBQcm9taXNlPHsgaGFzQWNjZXNzOiBib29sZWFuOyBlcnJvcj86IHN0cmluZyB9PiB7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGV4ZWNGaWxlTm9UaHJvdygnZ2gnLCBbXG4gICAgICAgICdhcGknLFxuICAgICAgICBgcmVwb3MvJHtyZXBvTmFtZX1gLFxuICAgICAgICAnLS1qcScsXG4gICAgICAgICcucGVybWlzc2lvbnMuYWRtaW4nLFxuICAgICAgXSlcblxuICAgICAgaWYgKHJlc3VsdC5jb2RlID09PSAwKSB7XG4gICAgICAgIGNvbnN0IGhhc0FkbWluID0gcmVzdWx0LnN0ZG91dC50cmltKCkgPT09ICd0cnVlJ1xuICAgICAgICByZXR1cm4geyBoYXNBY2Nlc3M6IGhhc0FkbWluIH1cbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICByZXN1bHQuc3RkZXJyLmluY2x1ZGVzKCc0MDQnKSB8fFxuICAgICAgICByZXN1bHQuc3RkZXJyLmluY2x1ZGVzKCdOb3QgRm91bmQnKVxuICAgICAgKSB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgaGFzQWNjZXNzOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjogJ3JlcG9zaXRvcnlfbm90X2ZvdW5kJyxcbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICByZXR1cm4geyBoYXNBY2Nlc3M6IGZhbHNlIH1cbiAgICB9IGNhdGNoIHtcbiAgICAgIHJldHVybiB7IGhhc0FjY2VzczogZmFsc2UgfVxuICAgIH1cbiAgfVxuXG4gIGFzeW5jIGZ1bmN0aW9uIGNoZWNrRXhpc3RpbmdXb3JrZmxvd0ZpbGUocmVwb05hbWU6IHN0cmluZyk6IFByb21pc2U8Ym9vbGVhbj4ge1xuICAgIGNvbnN0IGNoZWNrRmlsZVJlc3VsdCA9IGF3YWl0IGV4ZWNGaWxlTm9UaHJvdygnZ2gnLCBbXG4gICAgICAnYXBpJyxcbiAgICAgIGByZXBvcy8ke3JlcG9OYW1lfS9jb250ZW50cy8uZ2l0aHViL3dvcmtmbG93cy91bW1heWEueW1sYCxcbiAgICAgICctLWpxJyxcbiAgICAgICcuc2hhJyxcbiAgICBdKVxuXG4gICAgcmV0dXJuIGNoZWNrRmlsZVJlc3VsdC5jb2RlID09PSAwXG4gIH1cblxuICBhc3luYyBmdW5jdGlvbiBjaGVja0V4aXN0aW5nU2VjcmV0KCkge1xuICAgIGNvbnN0IGNoZWNrU2VjcmV0c1Jlc3VsdCA9IGF3YWl0IGV4ZWNGaWxlTm9UaHJvdygnZ2gnLCBbXG4gICAgICAnc2VjcmV0JyxcbiAgICAgICdsaXN0JyxcbiAgICAgICctLWFwcCcsXG4gICAgICAnYWN0aW9ucycsXG4gICAgICAnLS1yZXBvJyxcbiAgICAgIHN0YXRlLnNlbGVjdGVkUmVwb05hbWUsXG4gICAgXSlcblxuICAgIGlmIChjaGVja1NlY3JldHNSZXN1bHQuY29kZSA9PT0gMCkge1xuICAgICAgY29uc3QgbGluZXMgPSBjaGVja1NlY3JldHNSZXN1bHQuc3Rkb3V0LnNwbGl0KCdcXG4nKVxuICAgICAgY29uc3QgaGFzRnJpZW5kbGlLZXkgPSBzZWNyZXRMaXN0Q29udGFpbnMobGluZXMsIEZSSUVORExJX1BSSU1BUllfRU5WKVxuXG4gICAgICBpZiAoaGFzRnJpZW5kbGlLZXkpIHtcbiAgICAgICAgc2V0U3RhdGUocHJldiA9PiAoe1xuICAgICAgICAgIC4uLnByZXYsXG4gICAgICAgICAgc2VjcmV0RXhpc3RzOiB0cnVlLFxuICAgICAgICAgIHN0ZXA6ICdjaGVjay1leGlzdGluZy1zZWNyZXQnLFxuICAgICAgICB9KSlcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIC8vIE5vIGV4aXN0aW5nIHNlY3JldCBmb3VuZFxuICAgICAgICBpZiAoZXhpc3RpbmdBcGlLZXkpIHtcbiAgICAgICAgICAvLyBVc2VyIGhhcyBsb2NhbCBrZXksIHNraXAgdG8gY3JlYXRpbmcgd2l0aCBpdFxuICAgICAgICAgIHNldFN0YXRlKHByZXYgPT4gKHtcbiAgICAgICAgICAgIC4uLnByZXYsXG4gICAgICAgICAgICBhcGlLZXlPck9BdXRoVG9rZW46IGV4aXN0aW5nQXBpS2V5LFxuICAgICAgICAgICAgdXNlRXhpc3RpbmdLZXk6IHRydWUsXG4gICAgICAgICAgfSkpXG4gICAgICAgICAgYXdhaXQgcnVuU2V0dXBHaXRIdWJBY3Rpb25zKGV4aXN0aW5nQXBpS2V5LCBzdGF0ZS5zZWNyZXROYW1lKVxuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIC8vIE5vIGxvY2FsIGtleSwgZ28gdG8gQVBJIGtleSBzdGVwXG4gICAgICAgICAgc2V0U3RhdGUocHJldiA9PiAoeyAuLi5wcmV2LCBzdGVwOiAnYXBpLWtleScgfSkpXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgLy8gRXJyb3IgY2hlY2tpbmcgc2VjcmV0c1xuICAgICAgaWYgKGV4aXN0aW5nQXBpS2V5KSB7XG4gICAgICAgIC8vIFVzZXIgaGFzIGxvY2FsIGtleSwgc2tpcCB0byBjcmVhdGluZyB3aXRoIGl0XG4gICAgICAgIHNldFN0YXRlKHByZXYgPT4gKHtcbiAgICAgICAgICAuLi5wcmV2LFxuICAgICAgICAgIGFwaUtleU9yT0F1dGhUb2tlbjogZXhpc3RpbmdBcGlLZXksXG4gICAgICAgICAgdXNlRXhpc3RpbmdLZXk6IHRydWUsXG4gICAgICAgIH0pKVxuICAgICAgICBhd2FpdCBydW5TZXR1cEdpdEh1YkFjdGlvbnMoZXhpc3RpbmdBcGlLZXksIHN0YXRlLnNlY3JldE5hbWUpXG4gICAgICB9IGVsc2Uge1xuICAgICAgICAvLyBObyBsb2NhbCBrZXksIGdvIHRvIEFQSSBrZXkgc3RlcFxuICAgICAgICBzZXRTdGF0ZShwcmV2ID0+ICh7IC4uLnByZXYsIHN0ZXA6ICdhcGkta2V5JyB9KSlcbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICBjb25zdCBoYW5kbGVTdWJtaXQgPSBhc3luYyAoKSA9PiB7XG4gICAgaWYgKHN0YXRlLnN0ZXAgPT09ICd3YXJuaW5ncycpIHtcbiAgICAgIGxvZ0V2ZW50KCd0ZW5ndV9pbnN0YWxsX2dpdGh1Yl9hcHBfc3RlcF9jb21wbGV0ZWQnLCB7XG4gICAgICAgIHN0ZXA6ICd3YXJuaW5ncycgYXMgQW5hbHl0aWNzTWV0YWRhdGFfSV9WRVJJRklFRF9USElTX0lTX05PVF9DT0RFX09SX0ZJTEVQQVRIUyxcbiAgICAgIH0pXG4gICAgICBzZXRTdGF0ZShwcmV2ID0+ICh7IC4uLnByZXYsIHN0ZXA6ICdpbnN0YWxsLWFwcCcgfSkpXG4gICAgICBzZXRUaW1lb3V0KG9wZW5HaXRIdWJBcHBJbnN0YWxsYXRpb24sIDApXG4gICAgfSBlbHNlIGlmIChzdGF0ZS5zdGVwID09PSAnY2hvb3NlLXJlcG8nKSB7XG4gICAgICBsZXQgcmVwb05hbWUgPSBzdGF0ZS51c2VDdXJyZW50UmVwb1xuICAgICAgICA/IHN0YXRlLmN1cnJlbnRSZXBvXG4gICAgICAgIDogc3RhdGUuc2VsZWN0ZWRSZXBvTmFtZVxuXG4gICAgICBpZiAoIXJlcG9OYW1lLnRyaW0oKSkge1xuICAgICAgICByZXR1cm5cbiAgICAgIH1cblxuICAgICAgY29uc3QgcmVwb1dhcm5pbmdzOiBXYXJuaW5nW10gPSBbXVxuXG4gICAgICBpZiAocmVwb05hbWUuaW5jbHVkZXMoJ2dpdGh1Yi5jb20nKSkge1xuICAgICAgICBjb25zdCBtYXRjaCA9IHJlcG9OYW1lLm1hdGNoKC9naXRodWJcXC5jb21bOi9dKFteL10rXFwvW14vXSspKFxcLmdpdCk/JC8pXG4gICAgICAgIGlmICghbWF0Y2gpIHtcbiAgICAgICAgICByZXBvV2FybmluZ3MucHVzaCh7XG4gICAgICAgICAgICB0aXRsZTogJ0ludmFsaWQgR2l0SHViIFVSTCBmb3JtYXQnLFxuICAgICAgICAgICAgbWVzc2FnZTogJ1RoZSByZXBvc2l0b3J5IFVSTCBmb3JtYXQgYXBwZWFycyB0byBiZSBpbnZhbGlkLicsXG4gICAgICAgICAgICBpbnN0cnVjdGlvbnM6IFtcbiAgICAgICAgICAgICAgJ1VzZSBmb3JtYXQ6IG93bmVyL3JlcG8gb3IgaHR0cHM6Ly9naXRodWIuY29tL293bmVyL3JlcG8nLFxuICAgICAgICAgICAgICAnRXhhbXBsZTogdW15dW5zYW5nL1VNTUFZQScsXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0pXG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgcmVwb05hbWUgPSBtYXRjaFsxXT8ucmVwbGFjZSgvXFwuZ2l0JC8sICcnKSB8fCAnJ1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGlmICghcmVwb05hbWUuaW5jbHVkZXMoJy8nKSkge1xuICAgICAgICByZXBvV2FybmluZ3MucHVzaCh7XG4gICAgICAgICAgdGl0bGU6ICdSZXBvc2l0b3J5IGZvcm1hdCB3YXJuaW5nJyxcbiAgICAgICAgICBtZXNzYWdlOiAnUmVwb3NpdG9yeSBzaG91bGQgYmUgaW4gZm9ybWF0IFwib3duZXIvcmVwb1wiJyxcbiAgICAgICAgICBpbnN0cnVjdGlvbnM6IFtcbiAgICAgICAgICAgICdVc2UgZm9ybWF0OiBvd25lci9yZXBvJyxcbiAgICAgICAgICAgICdFeGFtcGxlOiB1bXl1bnNhbmcvVU1NQVlBJyxcbiAgICAgICAgICBdLFxuICAgICAgICB9KVxuICAgICAgfVxuXG4gICAgICBjb25zdCBwZXJtaXNzaW9uQ2hlY2sgPSBhd2FpdCBjaGVja1JlcG9zaXRvcnlQZXJtaXNzaW9ucyhyZXBvTmFtZSlcblxuICAgICAgaWYgKHBlcm1pc3Npb25DaGVjay5lcnJvciA9PT0gJ3JlcG9zaXRvcnlfbm90X2ZvdW5kJykge1xuICAgICAgICByZXBvV2FybmluZ3MucHVzaCh7XG4gICAgICAgICAgdGl0bGU6ICdSZXBvc2l0b3J5IG5vdCBmb3VuZCcsXG4gICAgICAgICAgbWVzc2FnZTogYFJlcG9zaXRvcnkgJHtyZXBvTmFtZX0gd2FzIG5vdCBmb3VuZCBvciB5b3UgZG9uJ3QgaGF2ZSBhY2Nlc3MuYCxcbiAgICAgICAgICBpbnN0cnVjdGlvbnM6IFtcbiAgICAgICAgICAgIGBDaGVjayB0aGF0IHRoZSByZXBvc2l0b3J5IG5hbWUgaXMgY29ycmVjdDogJHtyZXBvTmFtZX1gLFxuICAgICAgICAgICAgJ0Vuc3VyZSB5b3UgaGF2ZSBhY2Nlc3MgdG8gdGhpcyByZXBvc2l0b3J5JyxcbiAgICAgICAgICAgICdGb3IgcHJpdmF0ZSByZXBvc2l0b3JpZXMsIG1ha2Ugc3VyZSB5b3VyIEdpdEh1YiB0b2tlbiBoYXMgdGhlIFwicmVwb1wiIHNjb3BlJyxcbiAgICAgICAgICAgICdZb3UgY2FuIGFkZCB0aGUgcmVwbyBzY29wZSB3aXRoOiBnaCBhdXRoIHJlZnJlc2ggLWggZ2l0aHViLmNvbSAtcyByZXBvLHdvcmtmbG93JyxcbiAgICAgICAgICBdLFxuICAgICAgICB9KVxuICAgICAgfSBlbHNlIGlmICghcGVybWlzc2lvbkNoZWNrLmhhc0FjY2Vzcykge1xuICAgICAgICByZXBvV2FybmluZ3MucHVzaCh7XG4gICAgICAgICAgdGl0bGU6ICdBZG1pbiBwZXJtaXNzaW9ucyByZXF1aXJlZCcsXG4gICAgICAgICAgbWVzc2FnZTogYFlvdSBtaWdodCBuZWVkIGFkbWluIHBlcm1pc3Npb25zIG9uICR7cmVwb05hbWV9IHRvIHNldCB1cCBHaXRIdWIgQWN0aW9ucy5gLFxuICAgICAgICAgIGluc3RydWN0aW9uczogW1xuICAgICAgICAgICAgJ1JlcG9zaXRvcnkgYWRtaW5zIGNhbiBpbnN0YWxsIEdpdEh1YiBBcHBzIGFuZCBzZXQgc2VjcmV0cycsXG4gICAgICAgICAgICAnQXNrIGEgcmVwb3NpdG9yeSBhZG1pbiB0byBydW4gdGhpcyBjb21tYW5kIGlmIHNldHVwIGZhaWxzJyxcbiAgICAgICAgICAgICdBbHRlcm5hdGl2ZWx5LCB5b3UgY2FuIHVzZSB0aGUgbWFudWFsIHNldHVwIGluc3RydWN0aW9ucycsXG4gICAgICAgICAgXSxcbiAgICAgICAgfSlcbiAgICAgIH1cblxuICAgICAgY29uc3Qgd29ya2Zsb3dFeGlzdHMgPSBhd2FpdCBjaGVja0V4aXN0aW5nV29ya2Zsb3dGaWxlKHJlcG9OYW1lKVxuXG4gICAgICBpZiAocmVwb1dhcm5pbmdzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgY29uc3QgYWxsV2FybmluZ3MgPSBbLi4uc3RhdGUud2FybmluZ3MsIC4uLnJlcG9XYXJuaW5nc11cbiAgICAgICAgc2V0U3RhdGUocHJldiA9PiAoe1xuICAgICAgICAgIC4uLnByZXYsXG4gICAgICAgICAgc2VsZWN0ZWRSZXBvTmFtZTogcmVwb05hbWUsXG4gICAgICAgICAgd29ya2Zsb3dFeGlzdHMsXG4gICAgICAgICAgd2FybmluZ3M6IGFsbFdhcm5pbmdzLFxuICAgICAgICAgIHN0ZXA6ICd3YXJuaW5ncycsXG4gICAgICAgIH0pKVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbG9nRXZlbnQoJ3Rlbmd1X2luc3RhbGxfZ2l0aHViX2FwcF9zdGVwX2NvbXBsZXRlZCcsIHtcbiAgICAgICAgICBzdGVwOiAnY2hvb3NlLXJlcG8nIGFzIEFuYWx5dGljc01ldGFkYXRhX0lfVkVSSUZJRURfVEhJU19JU19OT1RfQ09ERV9PUl9GSUxFUEFUSFMsXG4gICAgICAgIH0pXG4gICAgICAgIHNldFN0YXRlKHByZXYgPT4gKHtcbiAgICAgICAgICAuLi5wcmV2LFxuICAgICAgICAgIHNlbGVjdGVkUmVwb05hbWU6IHJlcG9OYW1lLFxuICAgICAgICAgIHdvcmtmbG93RXhpc3RzLFxuICAgICAgICAgIHN0ZXA6ICdpbnN0YWxsLWFwcCcsXG4gICAgICAgIH0pKVxuICAgICAgICBzZXRUaW1lb3V0KG9wZW5HaXRIdWJBcHBJbnN0YWxsYXRpb24sIDApXG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChzdGF0ZS5zdGVwID09PSAnaW5zdGFsbC1hcHAnKSB7XG4gICAgICBsb2dFdmVudCgndGVuZ3VfaW5zdGFsbF9naXRodWJfYXBwX3N0ZXBfY29tcGxldGVkJywge1xuICAgICAgICBzdGVwOiAnaW5zdGFsbC1hcHAnIGFzIEFuYWx5dGljc01ldGFkYXRhX0lfVkVSSUZJRURfVEhJU19JU19OT1RfQ09ERV9PUl9GSUxFUEFUSFMsXG4gICAgICB9KVxuICAgICAgaWYgKHN0YXRlLndvcmtmbG93RXhpc3RzKSB7XG4gICAgICAgIHNldFN0YXRlKHByZXYgPT4gKHsgLi4ucHJldiwgc3RlcDogJ2NoZWNrLWV4aXN0aW5nLXdvcmtmbG93JyB9KSlcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHNldFN0YXRlKHByZXYgPT4gKHsgLi4ucHJldiwgc3RlcDogJ3NlbGVjdC13b3JrZmxvd3MnIH0pKVxuICAgICAgfVxuICAgIH0gZWxzZSBpZiAoc3RhdGUuc3RlcCA9PT0gJ2NoZWNrLWV4aXN0aW5nLXdvcmtmbG93Jykge1xuICAgICAgcmV0dXJuXG4gICAgfSBlbHNlIGlmIChzdGF0ZS5zdGVwID09PSAnc2VsZWN0LXdvcmtmbG93cycpIHtcbiAgICAgIC8vIEhhbmRsZWQgYnkgdGhlIFdvcmtmbG93TXVsdGlzZWxlY3REaWFsb2cgY29tcG9uZW50XG4gICAgICByZXR1cm5cbiAgICB9IGVsc2UgaWYgKHN0YXRlLnN0ZXAgPT09ICdjaGVjay1leGlzdGluZy1zZWNyZXQnKSB7XG4gICAgICBsb2dFdmVudCgndGVuZ3VfaW5zdGFsbF9naXRodWJfYXBwX3N0ZXBfY29tcGxldGVkJywge1xuICAgICAgICBzdGVwOiAnY2hlY2stZXhpc3Rpbmctc2VjcmV0JyBhcyBBbmFseXRpY3NNZXRhZGF0YV9JX1ZFUklGSUVEX1RISVNfSVNfTk9UX0NPREVfT1JfRklMRVBBVEhTLFxuICAgICAgfSlcbiAgICAgIGlmIChzdGF0ZS51c2VFeGlzdGluZ1NlY3JldCkge1xuICAgICAgICBhd2FpdCBydW5TZXR1cEdpdEh1YkFjdGlvbnMobnVsbCwgc3RhdGUuc2VjcmV0TmFtZSlcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIC8vIFVzZXIgd2FudHMgdG8gdXNlIGEgbmV3IHNlY3JldCBuYW1lIHdpdGggdGhlaXIgQVBJIGtleVxuICAgICAgICBhd2FpdCBydW5TZXR1cEdpdEh1YkFjdGlvbnMoc3RhdGUuYXBpS2V5T3JPQXV0aFRva2VuLCBzdGF0ZS5zZWNyZXROYW1lKVxuICAgICAgfVxuICAgIH0gZWxzZSBpZiAoc3RhdGUuc3RlcCA9PT0gJ2FwaS1rZXknKSB7XG4gICAgICAvLyBJbiB0aGUgbmV3IGZsb3csIGFwaS1rZXkgc3RlcCBvbmx5IGFwcGVhcnMgd2hlbiB1c2VyIGhhcyBubyBleGlzdGluZyBrZXlcbiAgICAgIC8vIFRoZXkgZWl0aGVyIGVudGVyZWQgYSBuZXcga2V5IG9yIHdpbGwgY3JlYXRlIE9BdXRoIHRva2VuXG4gICAgICBpZiAoc3RhdGUuc2VsZWN0ZWRBcGlLZXlPcHRpb24gPT09ICdvYXV0aCcpIHtcbiAgICAgICAgLy8gT0F1dGggZmxvdyBhbHJlYWR5IGhhbmRsZWQgYnkgaGFuZGxlQ3JlYXRlT0F1dGhUb2tlblxuICAgICAgICByZXR1cm5cbiAgICAgIH1cblxuICAgICAgLy8gSWYgdXNlciBzZWxlY3RlZCAnZXhpc3RpbmcnIG9wdGlvbiwgdXNlIHRoZSBleGlzdGluZyBBUEkga2V5XG4gICAgICBjb25zdCBhcGlLZXlUb1VzZSA9XG4gICAgICAgIHN0YXRlLnNlbGVjdGVkQXBpS2V5T3B0aW9uID09PSAnZXhpc3RpbmcnXG4gICAgICAgICAgPyBleGlzdGluZ0FwaUtleVxuICAgICAgICAgIDogc3RhdGUuYXBpS2V5T3JPQXV0aFRva2VuXG5cbiAgICAgIGlmICghYXBpS2V5VG9Vc2UpIHtcbiAgICAgICAgbG9nRXZlbnQoJ3Rlbmd1X2luc3RhbGxfZ2l0aHViX2FwcF9lcnJvcicsIHtcbiAgICAgICAgICByZWFzb246XG4gICAgICAgICAgICAnYXBpX2tleV9taXNzaW5nJyBhcyBBbmFseXRpY3NNZXRhZGF0YV9JX1ZFUklGSUVEX1RISVNfSVNfTk9UX0NPREVfT1JfRklMRVBBVEhTLFxuICAgICAgICB9KVxuICAgICAgICBzZXRTdGF0ZShwcmV2ID0+ICh7XG4gICAgICAgICAgLi4ucHJldixcbiAgICAgICAgICBzdGVwOiAnZXJyb3InLFxuICAgICAgICAgIGVycm9yOiAnQVBJIGtleSBpcyByZXF1aXJlZCcsXG4gICAgICAgIH0pKVxuICAgICAgICByZXR1cm5cbiAgICAgIH1cblxuICAgICAgLy8gU3RvcmUgdGhlIEFQSSBrZXkgYmVpbmcgdXNlZCAoZWl0aGVyIGV4aXN0aW5nIG9yIG5ld2x5IGVudGVyZWQpXG4gICAgICBzZXRTdGF0ZShwcmV2ID0+ICh7XG4gICAgICAgIC4uLnByZXYsXG4gICAgICAgIGFwaUtleU9yT0F1dGhUb2tlbjogYXBpS2V5VG9Vc2UsXG4gICAgICAgIHVzZUV4aXN0aW5nS2V5OiBzdGF0ZS5zZWxlY3RlZEFwaUtleU9wdGlvbiA9PT0gJ2V4aXN0aW5nJyxcbiAgICAgIH0pKVxuXG4gICAgICBjb25zdCBjaGVja1NlY3JldHNSZXN1bHQgPSBhd2FpdCBleGVjRmlsZU5vVGhyb3coJ2doJywgW1xuICAgICAgICAnc2VjcmV0JyxcbiAgICAgICAgJ2xpc3QnLFxuICAgICAgICAnLS1hcHAnLFxuICAgICAgICAnYWN0aW9ucycsXG4gICAgICAgICctLXJlcG8nLFxuICAgICAgICBzdGF0ZS5zZWxlY3RlZFJlcG9OYW1lLFxuICAgICAgXSlcblxuICAgICAgaWYgKGNoZWNrU2VjcmV0c1Jlc3VsdC5jb2RlID09PSAwKSB7XG4gICAgICAgIGNvbnN0IGxpbmVzID0gY2hlY2tTZWNyZXRzUmVzdWx0LnN0ZG91dC5zcGxpdCgnXFxuJylcbiAgICAgICAgY29uc3QgaGFzRnJpZW5kbGlLZXkgPSBzZWNyZXRMaXN0Q29udGFpbnMobGluZXMsIEZSSUVORExJX1BSSU1BUllfRU5WKVxuXG4gICAgICAgIGlmIChoYXNGcmllbmRsaUtleSkge1xuICAgICAgICAgIGxvZ0V2ZW50KCd0ZW5ndV9pbnN0YWxsX2dpdGh1Yl9hcHBfc3RlcF9jb21wbGV0ZWQnLCB7XG4gICAgICAgICAgICBzdGVwOiAnYXBpLWtleScgYXMgQW5hbHl0aWNzTWV0YWRhdGFfSV9WRVJJRklFRF9USElTX0lTX05PVF9DT0RFX09SX0ZJTEVQQVRIUyxcbiAgICAgICAgICB9KVxuICAgICAgICAgIHNldFN0YXRlKHByZXYgPT4gKHtcbiAgICAgICAgICAgIC4uLnByZXYsXG4gICAgICAgICAgICBzZWNyZXRFeGlzdHM6IHRydWUsXG4gICAgICAgICAgICBzdGVwOiAnY2hlY2stZXhpc3Rpbmctc2VjcmV0JyxcbiAgICAgICAgICB9KSlcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBsb2dFdmVudCgndGVuZ3VfaW5zdGFsbF9naXRodWJfYXBwX3N0ZXBfY29tcGxldGVkJywge1xuICAgICAgICAgICAgc3RlcDogJ2FwaS1rZXknIGFzIEFuYWx5dGljc01ldGFkYXRhX0lfVkVSSUZJRURfVEhJU19JU19OT1RfQ09ERV9PUl9GSUxFUEFUSFMsXG4gICAgICAgICAgfSlcbiAgICAgICAgICAvLyBObyBleGlzdGluZyBzZWNyZXQsIHByb2NlZWQgdG8gY3JlYXRpbmdcbiAgICAgICAgICBhd2FpdCBydW5TZXR1cEdpdEh1YkFjdGlvbnMoYXBpS2V5VG9Vc2UsIHN0YXRlLnNlY3JldE5hbWUpXG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGxvZ0V2ZW50KCd0ZW5ndV9pbnN0YWxsX2dpdGh1Yl9hcHBfc3RlcF9jb21wbGV0ZWQnLCB7XG4gICAgICAgICAgc3RlcDogJ2FwaS1rZXknIGFzIEFuYWx5dGljc01ldGFkYXRhX0lfVkVSSUZJRURfVEhJU19JU19OT1RfQ09ERV9PUl9GSUxFUEFUSFMsXG4gICAgICAgIH0pXG4gICAgICAgIC8vIEVycm9yIGNoZWNraW5nIHNlY3JldHMsIHByb2NlZWQgYW55d2F5XG4gICAgICAgIGF3YWl0IHJ1blNldHVwR2l0SHViQWN0aW9ucyhhcGlLZXlUb1VzZSwgc3RhdGUuc2VjcmV0TmFtZSlcbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICBjb25zdCBoYW5kbGVSZXBvVXJsQ2hhbmdlID0gKHZhbHVlOiBzdHJpbmcpID0+IHtcbiAgICBzZXRTdGF0ZShwcmV2ID0+ICh7IC4uLnByZXYsIHNlbGVjdGVkUmVwb05hbWU6IHZhbHVlIH0pKVxuICB9XG5cbiAgY29uc3QgaGFuZGxlQXBpS2V5Q2hhbmdlID0gKHZhbHVlOiBzdHJpbmcpID0+IHtcbiAgICBzZXRTdGF0ZShwcmV2ID0+ICh7IC4uLnByZXYsIGFwaUtleU9yT0F1dGhUb2tlbjogdmFsdWUgfSkpXG4gIH1cblxuICBjb25zdCBoYW5kbGVBcGlLZXlPcHRpb25DaGFuZ2UgPSAob3B0aW9uOiAnZXhpc3RpbmcnIHwgJ25ldycgfCAnb2F1dGgnKSA9PiB7XG4gICAgc2V0U3RhdGUocHJldiA9PiAoeyAuLi5wcmV2LCBzZWxlY3RlZEFwaUtleU9wdGlvbjogb3B0aW9uIH0pKVxuICB9XG5cbiAgY29uc3QgaGFuZGxlQ3JlYXRlT0F1dGhUb2tlbiA9IHVzZUNhbGxiYWNrKCgpID0+IHtcbiAgICBsb2dFdmVudCgndGVuZ3VfaW5zdGFsbF9naXRodWJfYXBwX3N0ZXBfY29tcGxldGVkJywge1xuICAgICAgc3RlcDogJ2FwaS1rZXknIGFzIEFuYWx5dGljc01ldGFkYXRhX0lfVkVSSUZJRURfVEhJU19JU19OT1RfQ09ERV9PUl9GSUxFUEFUSFMsXG4gICAgfSlcbiAgICBzZXRTdGF0ZShwcmV2ID0+ICh7IC4uLnByZXYsIHN0ZXA6ICdvYXV0aC1mbG93JyB9KSlcbiAgfSwgW10pXG5cbiAgY29uc3QgaGFuZGxlT0F1dGhTdWNjZXNzID0gdXNlQ2FsbGJhY2soXG4gICAgKHRva2VuOiBzdHJpbmcpID0+IHtcbiAgICAgIGxvZ0V2ZW50KCd0ZW5ndV9pbnN0YWxsX2dpdGh1Yl9hcHBfc3RlcF9jb21wbGV0ZWQnLCB7XG4gICAgICAgIHN0ZXA6ICdvYXV0aC1mbG93JyBhcyBBbmFseXRpY3NNZXRhZGF0YV9JX1ZFUklGSUVEX1RISVNfSVNfTk9UX0NPREVfT1JfRklMRVBBVEhTLFxuICAgICAgfSlcbiAgICAgIHNldFN0YXRlKHByZXYgPT4gKHtcbiAgICAgICAgLi4ucHJldixcbiAgICAgICAgYXBpS2V5T3JPQXV0aFRva2VuOiB0b2tlbixcbiAgICAgICAgdXNlRXhpc3RpbmdLZXk6IGZhbHNlLFxuICAgICAgICBzZWNyZXROYW1lOiBGUklFTkRMSV9QUklNQVJZX0VOVixcbiAgICAgICAgYXV0aFR5cGU6ICdhcGlfa2V5JyxcbiAgICAgIH0pKVxuICAgICAgdm9pZCBydW5TZXR1cEdpdEh1YkFjdGlvbnModG9rZW4sIEZSSUVORExJX1BSSU1BUllfRU5WKVxuICAgIH0sXG4gICAgW3J1blNldHVwR2l0SHViQWN0aW9uc10sXG4gIClcblxuICBjb25zdCBoYW5kbGVPQXV0aENhbmNlbCA9IHVzZUNhbGxiYWNrKCgpID0+IHtcbiAgICBzZXRTdGF0ZShwcmV2ID0+ICh7IC4uLnByZXYsIHN0ZXA6ICdhcGkta2V5JyB9KSlcbiAgfSwgW10pXG5cbiAgY29uc3QgaGFuZGxlU2VjcmV0TmFtZUNoYW5nZSA9ICh2YWx1ZTogc3RyaW5nKSA9PiB7XG4gICAgaWYgKHZhbHVlICYmICEvXlthLXpBLVowLTlfXSskLy50ZXN0KHZhbHVlKSkgcmV0dXJuXG4gICAgc2V0U3RhdGUocHJldiA9PiAoeyAuLi5wcmV2LCBzZWNyZXROYW1lOiB2YWx1ZSB9KSlcbiAgfVxuXG4gIGNvbnN0IGhhbmRsZVRvZ2dsZVVzZUN1cnJlbnRSZXBvID0gKHVzZUN1cnJlbnRSZXBvOiBib29sZWFuKSA9PiB7XG4gICAgc2V0U3RhdGUocHJldiA9PiAoe1xuICAgICAgLi4ucHJldixcbiAgICAgIHVzZUN1cnJlbnRSZXBvLFxuICAgICAgc2VsZWN0ZWRSZXBvTmFtZTogdXNlQ3VycmVudFJlcG8gPyBwcmV2LmN1cnJlbnRSZXBvIDogJycsXG4gICAgfSkpXG4gIH1cblxuICBjb25zdCBoYW5kbGVUb2dnbGVVc2VFeGlzdGluZ0tleSA9ICh1c2VFeGlzdGluZ0tleTogYm9vbGVhbikgPT4ge1xuICAgIHNldFN0YXRlKHByZXYgPT4gKHsgLi4ucHJldiwgdXNlRXhpc3RpbmdLZXkgfSkpXG4gIH1cblxuICBjb25zdCBoYW5kbGVUb2dnbGVVc2VFeGlzdGluZ1NlY3JldCA9ICh1c2VFeGlzdGluZ1NlY3JldDogYm9vbGVhbikgPT4ge1xuICAgIHNldFN0YXRlKHByZXYgPT4gKHtcbiAgICAgIC4uLnByZXYsXG4gICAgICB1c2VFeGlzdGluZ1NlY3JldCxcbiAgICAgIHNlY3JldE5hbWU6IHVzZUV4aXN0aW5nU2VjcmV0ID8gRlJJRU5ETElfUFJJTUFSWV9FTlYgOiAnJyxcbiAgICB9KSlcbiAgfVxuXG4gIGNvbnN0IGhhbmRsZVdvcmtmbG93QWN0aW9uID0gYXN5bmMgKGFjdGlvbjogJ3VwZGF0ZScgfCAnc2tpcCcgfCAnZXhpdCcpID0+IHtcbiAgICBpZiAoYWN0aW9uID09PSAnZXhpdCcpIHtcbiAgICAgIHByb3BzLm9uRG9uZSgnSW5zdGFsbGF0aW9uIGNhbmNlbGxlZCBieSB1c2VyJylcbiAgICAgIHJldHVyblxuICAgIH1cblxuICAgIGxvZ0V2ZW50KCd0ZW5ndV9pbnN0YWxsX2dpdGh1Yl9hcHBfc3RlcF9jb21wbGV0ZWQnLCB7XG4gICAgICBzdGVwOiAnY2hlY2stZXhpc3Rpbmctd29ya2Zsb3cnIGFzIEFuYWx5dGljc01ldGFkYXRhX0lfVkVSSUZJRURfVEhJU19JU19OT1RfQ09ERV9PUl9GSUxFUEFUSFMsXG4gICAgfSlcblxuICAgIHNldFN0YXRlKHByZXYgPT4gKHsgLi4ucHJldiwgd29ya2Zsb3dBY3Rpb246IGFjdGlvbiB9KSlcblxuICAgIGlmIChhY3Rpb24gPT09ICdza2lwJyB8fCBhY3Rpb24gPT09ICd1cGRhdGUnKSB7XG4gICAgICAvLyBDaGVjayBpZiB1c2VyIGhhcyBleGlzdGluZyBsb2NhbCBBUEkga2V5XG4gICAgICBpZiAoZXhpc3RpbmdBcGlLZXkpIHtcbiAgICAgICAgYXdhaXQgY2hlY2tFeGlzdGluZ1NlY3JldCgpXG4gICAgICB9IGVsc2Uge1xuICAgICAgICAvLyBObyBsb2NhbCBrZXksIGdvIHN0cmFpZ2h0IHRvIEFQSSBrZXkgc3RlcFxuICAgICAgICBzZXRTdGF0ZShwcmV2ID0+ICh7IC4uLnByZXYsIHN0ZXA6ICdhcGkta2V5JyB9KSlcbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICBmdW5jdGlvbiBoYW5kbGVEaXNtaXNzS2V5RG93bihlOiBLZXlib2FyZEV2ZW50KTogdm9pZCB7XG4gICAgZS5wcmV2ZW50RGVmYXVsdCgpXG4gICAgaWYgKHN0YXRlLnN0ZXAgPT09ICdzdWNjZXNzJykge1xuICAgICAgbG9nRXZlbnQoJ3Rlbmd1X2luc3RhbGxfZ2l0aHViX2FwcF9jb21wbGV0ZWQnLCB7fSlcbiAgICB9XG4gICAgcHJvcHMub25Eb25lKFxuICAgICAgc3RhdGUuc3RlcCA9PT0gJ3N1Y2Nlc3MnXG4gICAgICAgID8gJ0dpdEh1YiBBY3Rpb25zIHNldHVwIGNvbXBsZXRlISdcbiAgICAgICAgOiBzdGF0ZS5lcnJvclxuICAgICAgICAgID8gYENvdWxkbid0IGluc3RhbGwgR2l0SHViIEFwcDogJHtzdGF0ZS5lcnJvcn1cXG5Gb3IgbWFudWFsIHNldHVwIGluc3RydWN0aW9ucywgc2VlOiAke0dJVEhVQl9BQ1RJT05fU0VUVVBfRE9DU19VUkx9YFxuICAgICAgICAgIDogYEdpdEh1YiBBcHAgaW5zdGFsbGF0aW9uIGZhaWxlZFxcbkZvciBtYW51YWwgc2V0dXAgaW5zdHJ1Y3Rpb25zLCBzZWU6ICR7R0lUSFVCX0FDVElPTl9TRVRVUF9ET0NTX1VSTH1gLFxuICAgIClcbiAgfVxuXG4gIHN3aXRjaCAoc3RhdGUuc3RlcCkge1xuICAgIGNhc2UgJ2NoZWNrLWdoJzpcbiAgICAgIHJldHVybiA8Q2hlY2tHaXRIdWJTdGVwIC8+XG4gICAgY2FzZSAnd2FybmluZ3MnOlxuICAgICAgcmV0dXJuIChcbiAgICAgICAgPFdhcm5pbmdzU3RlcCB3YXJuaW5ncz17c3RhdGUud2FybmluZ3N9IG9uQ29udGludWU9e2hhbmRsZVN1Ym1pdH0gLz5cbiAgICAgIClcbiAgICBjYXNlICdjaG9vc2UtcmVwbyc6XG4gICAgICByZXR1cm4gKFxuICAgICAgICA8Q2hvb3NlUmVwb1N0ZXBcbiAgICAgICAgICBjdXJyZW50UmVwbz17c3RhdGUuY3VycmVudFJlcG99XG4gICAgICAgICAgdXNlQ3VycmVudFJlcG89e3N0YXRlLnVzZUN1cnJlbnRSZXBvfVxuICAgICAgICAgIHJlcG9Vcmw9e3N0YXRlLnNlbGVjdGVkUmVwb05hbWV9XG4gICAgICAgICAgb25SZXBvVXJsQ2hhbmdlPXtoYW5kbGVSZXBvVXJsQ2hhbmdlfVxuICAgICAgICAgIG9uVG9nZ2xlVXNlQ3VycmVudFJlcG89e2hhbmRsZVRvZ2dsZVVzZUN1cnJlbnRSZXBvfVxuICAgICAgICAgIG9uU3VibWl0PXtoYW5kbGVTdWJtaXR9XG4gICAgICAgIC8+XG4gICAgICApXG4gICAgY2FzZSAnaW5zdGFsbC1hcHAnOlxuICAgICAgcmV0dXJuIChcbiAgICAgICAgPEluc3RhbGxBcHBTdGVwXG4gICAgICAgICAgcmVwb1VybD17c3RhdGUuc2VsZWN0ZWRSZXBvTmFtZX1cbiAgICAgICAgICBvblN1Ym1pdD17aGFuZGxlU3VibWl0fVxuICAgICAgICAvPlxuICAgICAgKVxuICAgIGNhc2UgJ2NoZWNrLWV4aXN0aW5nLXdvcmtmbG93JzpcbiAgICAgIHJldHVybiAoXG4gICAgICAgIDxFeGlzdGluZ1dvcmtmbG93U3RlcFxuICAgICAgICAgIHJlcG9OYW1lPXtzdGF0ZS5zZWxlY3RlZFJlcG9OYW1lfVxuICAgICAgICAgIG9uU2VsZWN0QWN0aW9uPXtoYW5kbGVXb3JrZmxvd0FjdGlvbn1cbiAgICAgICAgLz5cbiAgICAgIClcbiAgICBjYXNlICdjaGVjay1leGlzdGluZy1zZWNyZXQnOlxuICAgICAgcmV0dXJuIChcbiAgICAgICAgPENoZWNrRXhpc3RpbmdTZWNyZXRTdGVwXG4gICAgICAgICAgdXNlRXhpc3RpbmdTZWNyZXQ9e3N0YXRlLnVzZUV4aXN0aW5nU2VjcmV0fVxuICAgICAgICAgIHNlY3JldE5hbWU9e3N0YXRlLnNlY3JldE5hbWV9XG4gICAgICAgICAgb25Ub2dnbGVVc2VFeGlzdGluZ1NlY3JldD17aGFuZGxlVG9nZ2xlVXNlRXhpc3RpbmdTZWNyZXR9XG4gICAgICAgICAgb25TZWNyZXROYW1lQ2hhbmdlPXtoYW5kbGVTZWNyZXROYW1lQ2hhbmdlfVxuICAgICAgICAgIG9uU3VibWl0PXtoYW5kbGVTdWJtaXR9XG4gICAgICAgIC8+XG4gICAgICApXG4gICAgY2FzZSAnYXBpLWtleSc6XG4gICAgICByZXR1cm4gKFxuICAgICAgICA8QXBpS2V5U3RlcFxuICAgICAgICAgIGV4aXN0aW5nQXBpS2V5PXtleGlzdGluZ0FwaUtleX1cbiAgICAgICAgICB1c2VFeGlzdGluZ0tleT17c3RhdGUudXNlRXhpc3RpbmdLZXl9XG4gICAgICAgICAgYXBpS2V5T3JPQXV0aFRva2VuPXtzdGF0ZS5hcGlLZXlPck9BdXRoVG9rZW59XG4gICAgICAgICAgb25BcGlLZXlDaGFuZ2U9e2hhbmRsZUFwaUtleUNoYW5nZX1cbiAgICAgICAgICBvblRvZ2dsZVVzZUV4aXN0aW5nS2V5PXtoYW5kbGVUb2dnbGVVc2VFeGlzdGluZ0tleX1cbiAgICAgICAgICBvblN1Ym1pdD17aGFuZGxlU3VibWl0fVxuICAgICAgICAgIG9uQ3JlYXRlT0F1dGhUb2tlbj17XG4gICAgICAgICAgICBpc0FudGhyb3BpY0F1dGhFbmFibGVkKCkgPyBoYW5kbGVDcmVhdGVPQXV0aFRva2VuIDogdW5kZWZpbmVkXG4gICAgICAgICAgfVxuICAgICAgICAgIHNlbGVjdGVkT3B0aW9uPXtzdGF0ZS5zZWxlY3RlZEFwaUtleU9wdGlvbn1cbiAgICAgICAgICBvblNlbGVjdE9wdGlvbj17aGFuZGxlQXBpS2V5T3B0aW9uQ2hhbmdlfVxuICAgICAgICAvPlxuICAgICAgKVxuICAgIGNhc2UgJ2NyZWF0aW5nJzpcbiAgICAgIHJldHVybiAoXG4gICAgICAgIDxDcmVhdGluZ1N0ZXBcbiAgICAgICAgICBjdXJyZW50V29ya2Zsb3dJbnN0YWxsU3RlcD17c3RhdGUuY3VycmVudFdvcmtmbG93SW5zdGFsbFN0ZXB9XG4gICAgICAgICAgc2VjcmV0RXhpc3RzPXtzdGF0ZS5zZWNyZXRFeGlzdHN9XG4gICAgICAgICAgdXNlRXhpc3RpbmdTZWNyZXQ9e3N0YXRlLnVzZUV4aXN0aW5nU2VjcmV0fVxuICAgICAgICAgIHNlY3JldE5hbWU9e3N0YXRlLnNlY3JldE5hbWV9XG4gICAgICAgICAgc2tpcFdvcmtmbG93PXtzdGF0ZS53b3JrZmxvd0FjdGlvbiA9PT0gJ3NraXAnfVxuICAgICAgICAgIHNlbGVjdGVkV29ya2Zsb3dzPXtzdGF0ZS5zZWxlY3RlZFdvcmtmbG93c31cbiAgICAgICAgLz5cbiAgICAgIClcbiAgICBjYXNlICdzdWNjZXNzJzpcbiAgICAgIHJldHVybiAoXG4gICAgICAgIDxCb3ggdGFiSW5kZXg9ezB9IGF1dG9Gb2N1cyBvbktleURvd249e2hhbmRsZURpc21pc3NLZXlEb3dufT5cbiAgICAgICAgICA8U3VjY2Vzc1N0ZXBcbiAgICAgICAgICAgIHNlY3JldEV4aXN0cz17c3RhdGUuc2VjcmV0RXhpc3RzfVxuICAgICAgICAgICAgdXNlRXhpc3RpbmdTZWNyZXQ9e3N0YXRlLnVzZUV4aXN0aW5nU2VjcmV0fVxuICAgICAgICAgICAgc2VjcmV0TmFtZT17c3RhdGUuc2VjcmV0TmFtZX1cbiAgICAgICAgICAgIHNraXBXb3JrZmxvdz17c3RhdGUud29ya2Zsb3dBY3Rpb24gPT09ICdza2lwJ31cbiAgICAgICAgICAvPlxuICAgICAgICA8L0JveD5cbiAgICAgIClcbiAgICBjYXNlICdlcnJvcic6XG4gICAgICByZXR1cm4gKFxuICAgICAgICA8Qm94IHRhYkluZGV4PXswfSBhdXRvRm9jdXMgb25LZXlEb3duPXtoYW5kbGVEaXNtaXNzS2V5RG93bn0+XG4gICAgICAgICAgPEVycm9yU3RlcFxuICAgICAgICAgICAgZXJyb3I9e3N0YXRlLmVycm9yfVxuICAgICAgICAgICAgZXJyb3JSZWFzb249e3N0YXRlLmVycm9yUmVhc29ufVxuICAgICAgICAgICAgZXJyb3JJbnN0cnVjdGlvbnM9e3N0YXRlLmVycm9ySW5zdHJ1Y3Rpb25zfVxuICAgICAgICAgIC8+XG4gICAgICAgIDwvQm94PlxuICAgICAgKVxuICAgIGNhc2UgJ3NlbGVjdC13b3JrZmxvd3MnOlxuICAgICAgcmV0dXJuIChcbiAgICAgICAgPFdvcmtmbG93TXVsdGlzZWxlY3REaWFsb2dcbiAgICAgICAgICBkZWZhdWx0U2VsZWN0aW9ucz17c3RhdGUuc2VsZWN0ZWRXb3JrZmxvd3N9XG4gICAgICAgICAgb25TdWJtaXQ9e3NlbGVjdGVkV29ya2Zsb3dzID0+IHtcbiAgICAgICAgICAgIGxvZ0V2ZW50KCd0ZW5ndV9pbnN0YWxsX2dpdGh1Yl9hcHBfc3RlcF9jb21wbGV0ZWQnLCB7XG4gICAgICAgICAgICAgIHN0ZXA6ICdzZWxlY3Qtd29ya2Zsb3dzJyBhcyBBbmFseXRpY3NNZXRhZGF0YV9JX1ZFUklGSUVEX1RISVNfSVNfTk9UX0NPREVfT1JfRklMRVBBVEhTLFxuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIHNldFN0YXRlKHByZXYgPT4gKHtcbiAgICAgICAgICAgICAgLi4ucHJldixcbiAgICAgICAgICAgICAgc2VsZWN0ZWRXb3JrZmxvd3MsXG4gICAgICAgICAgICB9KSlcbiAgICAgICAgICAgIC8vIENoZWNrIGlmIHVzZXIgaGFzIGV4aXN0aW5nIGxvY2FsIEFQSSBrZXlcbiAgICAgICAgICAgIGlmIChleGlzdGluZ0FwaUtleSkge1xuICAgICAgICAgICAgICB2b2lkIGNoZWNrRXhpc3RpbmdTZWNyZXQoKVxuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgLy8gTm8gbG9jYWwga2V5LCBnbyBzdHJhaWdodCB0byBBUEkga2V5IHN0ZXBcbiAgICAgICAgICAgICAgc2V0U3RhdGUocHJldiA9PiAoeyAuLi5wcmV2LCBzdGVwOiAnYXBpLWtleScgfSkpXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfX1cbiAgICAgICAgLz5cbiAgICAgIClcbiAgICBjYXNlICdvYXV0aC1mbG93JzpcbiAgICAgIHJldHVybiAoXG4gICAgICAgIDxPQXV0aEZsb3dTdGVwXG4gICAgICAgICAgb25TdWNjZXNzPXtoYW5kbGVPQXV0aFN1Y2Nlc3N9XG4gICAgICAgICAgb25DYW5jZWw9e2hhbmRsZU9BdXRoQ2FuY2VsfVxuICAgICAgICAvPlxuICAgICAgKVxuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBjYWxsKFxuICBvbkRvbmU6IExvY2FsSlNYQ29tbWFuZE9uRG9uZSxcbik6IFByb21pc2U8UmVhY3QuUmVhY3ROb2RlPiB7XG4gIHJldHVybiA8SW5zdGFsbEdpdEh1YkFwcCBvbkRvbmU9e29uRG9uZX0gLz5cbn1cbiJdLCJtYXBwaW5ncyI6IkFBQUEsU0FBU0EsS0FBSyxRQUFRLE9BQU87QUFDN0IsT0FBT0MsS0FBSyxJQUFJQyxXQUFXLEVBQUVDLFFBQVEsUUFBUSxPQUFPO0FBQ3BELFNBQ0UsS0FBS0MsMERBQTBELEVBQy9EQyxRQUFRLFFBQ0gsaUNBQWlDO0FBQ3hDLFNBQVNDLHlCQUF5QixRQUFRLCtDQUErQztBQUN6RixTQUFTQyw0QkFBNEIsUUFBUSwrQkFBK0I7QUFDNUUsU0FBU0MsOEJBQThCLFFBQVEsK0NBQStDO0FBQzlGLGNBQWNDLGFBQWEsUUFBUSxvQ0FBb0M7QUFDdkUsU0FBU0MsR0FBRyxRQUFRLGNBQWM7QUFDbEMsY0FBY0MscUJBQXFCLFFBQVEsd0JBQXdCO0FBQ25FLFNBQVNDLGtCQUFrQixFQUFFQyxzQkFBc0IsUUFBUSxxQkFBcUI7QUFDaEYsU0FBU0MsV0FBVyxRQUFRLHdC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