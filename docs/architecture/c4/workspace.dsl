workspace "UMMAYA C4 Views" "Small architecture views for the UMMAYA documentation site." {
  !identifiers hierarchical

  model {
    citizen = person "Citizen"
    evaluator = person "Evaluator"

    ummaya = softwareSystem "UMMAYA" {
      tui = container "UI"
      queryEngine = container "Query Engine" {
        context = component "Context"
        retrieve = component "Retrieve"
        primitives = component "Primitives"
        validate = component "Validate"
        gate = component "Gate"
        dispatch = component "Dispatch"
        stop = component "Stop"
      }
      contextStore = container "Sessions"
      toolRegistry = container "Registry"
      permissionPipeline = container "Permission"
      adapterLayer = container "Adapters"
      llmClient = container "K-EXAONE Client"
      docsSite = container "Docs"
    }

    friendli = softwareSystem "K-EXAONE"
    publicApis = softwareSystem "Public APIs"
    officialChannels = softwareSystem "Official Channels"
    cloudflarePages = softwareSystem "Cloudflare Pages"
    githubActions = softwareSystem "GitHub Actions"

    citizen -> ummaya "ask"
    citizen -> ummaya.tui "ask"
    evaluator -> ummaya.docsSite "read"

    ummaya -> friendli "reason"
    ummaya -> publicApis "Live"
    ummaya -> officialChannels "Live/Mock/Handoff"

    ummaya.tui -> ummaya.queryEngine "route"
    ummaya.queryEngine -> ummaya.contextStore "context"
    ummaya.queryEngine -> ummaya.toolRegistry "select"
    ummaya.queryEngine -> ummaya.llmClient "reason"
    ummaya.llmClient -> friendli "model"
    ummaya.queryEngine -> ummaya.permissionPipeline "gate"
    ummaya.permissionPipeline -> ummaya.adapterLayer "allow"
    ummaya.queryEngine -> ummaya.adapterLayer "call"
    ummaya.adapterLayer -> publicApis "Live"
    ummaya.adapterLayer -> officialChannels "Mock/Handoff"
    ummaya.adapterLayer -> ummaya.queryEngine "evidence"
    ummaya.queryEngine -> ummaya.tui "answer"

    ummaya.queryEngine.context -> ummaya.queryEngine.retrieve "narrow"
    ummaya.queryEngine.retrieve -> ummaya.queryEngine.primitives "surface"
    ummaya.queryEngine.primitives -> ummaya.queryEngine.validate "shape"
    ummaya.queryEngine.validate -> ummaya.queryEngine.gate "safe?"
    ummaya.queryEngine.gate -> ummaya.queryEngine.dispatch "run"
    ummaya.queryEngine.dispatch -> ummaya.queryEngine.stop "decide"
    ummaya.queryEngine.primitives -> ummaya.toolRegistry "adapter"
    ummaya.queryEngine.primitives -> ummaya.permissionPipeline "boundary"
    ummaya.queryEngine.dispatch -> ummaya.adapterLayer "execute"

    githubActions -> ummaya.docsSite "build"
    githubActions -> cloudflarePages "deploy"
    cloudflarePages -> ummaya.docsSite "serve"
  }

  views {
    systemContext ummaya "01-national-ax-context" "Where UMMAYA sits." {
      include citizen ummaya friendli publicApis officialChannels
      autoLayout lr
    }

    dynamic ummaya "02-query-loop" "One query loop." {
      citizen -> ummaya.tui "ask"
      ummaya.tui -> ummaya.queryEngine "route"
      ummaya.queryEngine -> ummaya.contextStore "context"
      ummaya.queryEngine -> ummaya.toolRegistry "select"
      ummaya.queryEngine -> ummaya.llmClient "reason"
      ummaya.llmClient -> friendli "model"
      ummaya.queryEngine -> ummaya.tui "answer"
      autoLayout lr
    }

    component ummaya.queryEngine "03-query-engine-core" "Inside the query engine." {
      include ummaya.queryEngine.context ummaya.queryEngine.retrieve ummaya.queryEngine.primitives ummaya.queryEngine.validate ummaya.queryEngine.gate ummaya.queryEngine.dispatch ummaya.queryEngine.stop
      autoLayout lr
    }

    dynamic ummaya "04-public-lookup-flow" "Public lookup path." {
      citizen -> ummaya.tui "ask"
      ummaya.tui -> ummaya.queryEngine "route"
      ummaya.queryEngine -> ummaya.toolRegistry "select"
      ummaya.queryEngine -> ummaya.adapterLayer "find"
      ummaya.adapterLayer -> publicApis "Live"
      ummaya.adapterLayer -> ummaya.queryEngine "evidence"
      ummaya.queryEngine -> ummaya.tui "answer"
      autoLayout lr
    }

    dynamic ummaya "05-protected-handoff-flow" "Protected action path." {
      citizen -> ummaya.tui "ask"
      ummaya.tui -> ummaya.queryEngine "route"
      ummaya.queryEngine -> ummaya.permissionPipeline "check"
      ummaya.permissionPipeline -> ummaya.adapterLayer "allow"
      ummaya.adapterLayer -> officialChannels "Handoff"
      ummaya.adapterLayer -> ummaya.queryEngine "evidence"
      ummaya.queryEngine -> ummaya.tui "stop"
      autoLayout lr
    }

    dynamic ummaya "06-docs-publish-flow" "Docs publishing path." {
      evaluator -> ummaya.docsSite "read"
      githubActions -> ummaya.docsSite "build"
      githubActions -> cloudflarePages "deploy"
      cloudflarePages -> ummaya.docsSite "serve"
      autoLayout lr
    }

    styles {
      element "Person" {
        shape Person
        background #f8fafc
        color #111827
        stroke #475569
      }
      element "Software System" {
        background #e0f2fe
        color #0f172a
        stroke #0369a1
      }
      element "Container" {
        background #ecfdf5
        color #052e16
        stroke #047857
      }
      element "Component" {
        background #fefce8
        color #422006
        stroke #a16207
      }
      relationship "Relationship" {
        color #475569
        thickness 2
      }
    }
  }
}
