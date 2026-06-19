export const PR_TITLE = 'Add UMMAYA GitHub Workflow'

export const GITHUB_ACTION_SETUP_DOCS_URL =
  'https://ummaya-docs.pages.dev/en/'

export const WORKFLOW_CONTENT = `name: UMMAYA

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
  issues:
    types: [opened, assigned]
  pull_request_review:
    types: [submitted]

jobs:
  ummaya:
    if: |
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@ummaya')) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@ummaya')) ||
      (github.event_name == 'pull_request_review' && contains(github.event.review.body, '@ummaya')) ||
      (github.event_name == 'issues' && (contains(github.event.issue.body, '@ummaya') || contains(github.event.issue.title, '@ummaya')))
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
      issues: read
      id-token: write
      actions: read # Required for UMMAYA to read CI results on PRs
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Install UMMAYA
        run: npm install -g ummaya

      - name: Verify UMMAYA
        id: ummaya
        env:
          UMMAYA_FRIENDLI_TOKEN: \${{ secrets.UMMAYA_FRIENDLI_TOKEN }}
        run: ummaya --version

      # See https://ummaya-docs.pages.dev/en/ for available options

`

export const PR_BODY = `## Installing UMMAYA GitHub App

This PR adds a GitHub Actions workflow that enables UMMAYA integration in our repository.

### What is UMMAYA?

[UMMAYA](https://ummaya-docs.pages.dev/en/) is an AI agent harness that can help with:
- Bug fixes and improvements  
- Documentation updates
- Implementing new features
- Code reviews and suggestions
- Writing tests
- And more!

### How it works

Once this PR is merged, @ummaya mentions in pull requests and issues will trigger a GitHub Actions smoke check for the repository's UMMAYA runtime.
The generated workflow verifies that the packaged UMMAYA CLI can install and start with the configured FriendliAI credential. Extend it from the UMMAYA documentation before enabling repository-specific automation.

### Important Notes

- **This workflow won't take effect until this PR is merged**
- **@ummaya mentions won't work until after the merge is complete**
- The workflow runs automatically whenever UMMAYA is mentioned in PR or issue comments
- The generated workflow is a runtime smoke check until repository-specific automation is added

### Security

- Our FriendliAI API key is securely stored as a GitHub Actions secret
- Only users with write access to the repository can trigger the workflow
- All UMMAYA runs are stored in the GitHub Actions run history
- Review the workflow file before adding write scopes, repository mutations, or project-specific commands.

There's more information in the [UMMAYA documentation](https://ummaya-docs.pages.dev/en/).

After merging this PR, mention @ummaya in a comment on any PR to verify the runtime smoke path.`

export const CODE_REVIEW_PLUGIN_WORKFLOW_CONTENT = `name: UMMAYA Review

on:
  pull_request:
    types: [opened, synchronize, ready_for_review, reopened]
    # Optional: Only run on specific file changes
    # paths:
    #   - "src/**/*.ts"
    #   - "src/**/*.tsx"
    #   - "src/**/*.js"
    #   - "src/**/*.jsx"

jobs:
  ummaya-review:
    # Optional: Filter by PR author
    # if: |
    #   github.event.pull_request.user.login == 'external-contributor' ||
    #   github.event.pull_request.user.login == 'new-developer' ||
    #   github.event.pull_request.author_association == 'FIRST_TIME_CONTRIBUTOR'

    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
      issues: read
      id-token: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Install UMMAYA
        run: npm install -g ummaya

      - name: Verify UMMAYA Review Runtime
        id: ummaya-review
        env:
          UMMAYA_FRIENDLI_TOKEN: \${{ secrets.UMMAYA_FRIENDLI_TOKEN }}
        run: ummaya --version

      # See https://ummaya-docs.pages.dev/en/ for available options

`
