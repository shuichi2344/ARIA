# ARIA System Flow Charts

> Detailed flow diagrams for each major module in the ARIA platform.

---

## 1. Account Module Flow

```mermaid
flowchart TD
    Start([Start]) --> A{User logged in?}
    A -->|Yes| Dashboard[View Dashboard]
    A -->|No| B{Has existing account?}
    
    %% --- Login Path ---
    B -->|Yes| C[Enter Login Details<br/>email + password]
    C --> D{Correct credentials?}
    D -->|Yes| E{Has business profile?}
    E -->|Yes| Dashboard
    E -->|No| Onboarding[Redirect to Onboarding]
    D -->|No| F{Forgot password?}
    F -->|No| C
    
    %% --- Forgot Password Path ---
    F -->|Yes| G[Enter email address]
    G --> H{Valid email?}
    H -->|No| G
    H -->|Yes| I[Password reset email sent]
    I --> J[User clicks email link]
    J --> K[View Reset Password page]
    K --> L[Enter new password]
    L --> M{Valid password?<br/>6+ chars, uppercase,<br/>number, special char}
    M -->|No| L
    M -->|Yes| N[Account password updated]
    N --> C
    
    %% --- Registration Path ---
    B -->|No| O[Enter account details<br/>email + password]
    O --> P{Valid email and<br/>strong password?}
    P -->|No| O
    P -->|Yes| Q{Email linked to<br/>existing account?}
    Q -->|Yes| R[Prompt user to<br/>login instead]
    R --> C
    Q -->|No| S[Account created]
    S --> Onboarding
    
    %% --- Change Password (from Dashboard) ---
    Dashboard --> T{Change password?}
    T -->|No| End([End])
    T -->|Yes| U[Enter current password<br/>+ new password]
    U --> V{Current password correct<br/>AND new password valid?}
    V -->|No| U
    V -->|Yes| W[Password updated]
    W --> Dashboard
```

---

## 2. Onboarding Module Flow

```mermaid
flowchart TD
    Start([User lands on /onboarding]) --> S1[Step 1: Business Info<br/>name, type, category,<br/>years operating, USPs]
    S1 --> S2[Step 2: Location<br/>state, district, city]
    S2 --> S3[Step 3: AI Analysis]
    
    S3 --> LLM[POST /api/business/analyze]
    LLM --> Build[Build prompt with<br/>business name, type,<br/>location, USPs]
    Build --> Call[LLMClient.generate<br/>Ilmu AI / Ollama fallback]
    Call --> Parse{Valid JSON response?}
    Parse -->|No| Retry{Retries left?}
    Retry -->|Yes| Call
    Retry -->|No| Error[Show error]
    Parse -->|Yes| Display[Display AI-generated profile:<br/>customer type, target customers,<br/>income levels, price ranges]
    
    Display --> S4[Step 4: Review all info]
    S4 --> Confirm{User confirms?}
    Confirm -->|Edit| S1
    Confirm -->|Yes| Save[POST /api/business/profile<br/>Save to database]
    Save --> Done[Redirect to Dashboard]
```

---

## 3. Simulation Flow (End-to-End)

```mermaid
flowchart TD
    Start([User asks question<br/>in ChatPanel]) --> Suggest[POST /api/simulation/suggest]
    
    %% --- Scenario Generation ---
    Suggest --> Context{Real-world<br/>context enabled?}
    Context -->|Yes| Fetch[Fetch News API +<br/>DOSM data + Calendar]
    Context -->|No| Skip[Skip external context]
    Fetch --> BuildPrompt
    Skip --> BuildPrompt[Build prompt with<br/>business profile + context]
    BuildPrompt --> GenScenarios[LLM generates 2-5 scenarios]
    GenScenarios --> ShowScenarios[Display scenarios to user]
    
    %% --- Simulation Start ---
    ShowScenarios --> Select[User selects scenario<br/>+ configures settings]
    Select --> StartSim[POST /api/simulation/start]
    
    %% --- Agent Generation ---
    StartSim --> Cache{Agent cache hit?}
    Cache -->|Yes| Reuse[Reuse cached agents<br/>reset per-sim state]
    Cache -->|No| Generate[Generate synthetic population<br/>via IPF + DOSM data]
    Generate --> Profiles[LLM generates personality<br/>profiles in batches]
    Profiles --> CacheStore[Store in agent cache]
    CacheStore --> CreateMesa[Create Mesa model + agents]
    Reuse --> CreateMesa
    
    %% --- Simulation Execution ---
    CreateMesa --> SSE[Open SSE stream to frontend]
    SSE --> Phase1[Phase 1: Independent Decisions<br/>Each agent decides visit/skip/churn]
    Phase1 --> Phase2[Phase 2: Peer Influence<br/>Connected agents reconsider]
    Phase2 --> Metrics[Aggregate weekly metrics]
    Metrics --> MoreWeeks{More weeks?}
    MoreWeeks -->|Yes| Phase1
    MoreWeeks -->|No| Report[Generate report:<br/>risk level, breakdown,<br/>recommendations]
    
    %% --- Output ---
    Report --> SaveDB[Save to database]
    SaveDB --> Display[Display report in chat<br/>+ PDF download option]
```

---

## 4. Population Generation Flow (IPF)

```mermaid
flowchart TD
    Start([Simulation start]) --> Type{Customer type?}
    
    Type -->|B2C| DOSM[Fetch DOSM demographics<br/>for business district]
    DOSM --> Marginals[Extract age + income<br/>marginal distributions]
    Marginals --> Constraints{Demographic<br/>constraints set?}
    Constraints -->|Yes| Filter[Filter to selected<br/>income levels + age groups]
    Constraints -->|No| Full[Use full distributions]
    Filter --> IPF
    Full --> IPF[Run IPF Engine<br/>match joint distribution<br/>to marginals]
    IPF --> Converged{Converged?}
    Converged -->|Yes| Sample[Sample agents from<br/>joint distribution]
    Converged -->|No| Fallback[Fallback: random sampling]
    Sample --> Attributes[Assign attributes:<br/>spending, loyalty,<br/>payment preferences]
    Fallback --> Attributes
    
    Type -->|B2B| B2BGen[Generate business agents<br/>from b2b_profile data<br/>sizes + segments]
    B2BGen --> Attributes
    
    Type -->|HYBRID| Split[Split by b2b_percentage]
    Split --> B2BGen
    Split --> DOSM
    
    Attributes --> Done([Return agent list])
```

---

## 5. LLM Integration Flow (Ilmu AI + Ollama Failover)

```mermaid
flowchart TD
    Start([LLM request]) --> Check{ILMU_API_KEY<br/>configured?}
    
    %% --- Ilmu AI Path ---
    Check -->|Yes| Ilmu[Try Ilmu AI<br/>POST api.ilmu.ai/v1/chat/completions]
    Ilmu --> IlmuOK{Success?}
    IlmuOK -->|Yes| ReturnIlmu([Return response<br/>provider: ilmu])
    IlmuOK -->|No| IlmuRetry{Retries left?}
    IlmuRetry -->|Yes| IlmuWait[Wait with backoff] --> Ilmu
    IlmuRetry -->|No| LogWarn[Log: Ilmu failed,<br/>falling back to Ollama]
    
    %% --- Ollama Fallback ---
    Check -->|No| Ollama
    LogWarn --> Ollama[Try Ollama<br/>POST localhost:11434/api/generate]
    Ollama --> OllamaOK{Success?}
    OllamaOK -->|Yes| ReturnOllama([Return response<br/>provider: ollama])
    OllamaOK -->|No| OllamaRetry{Retries left?}
    OllamaRetry -->|Yes| OllamaWait[Wait with backoff] --> Ollama
    OllamaRetry -->|No| Fail([Raise LLMClientError:<br/>All providers failed])
```

---

## 6. Chat & Session Flow

```mermaid
flowchart TD
    Start([User opens dashboard]) --> Init[chatSessionRef = null]
    Init --> Send{User sends message?}
    Send -->|Yes| Display[Display in UI]
    Display --> Persist[POST /api/chat/message]
    Persist --> HasSession{session_id exists?}
    HasSession -->|No| Create[Create new chat_session<br/>in database]
    Create --> Store[Store session_id in ref]
    HasSession -->|Yes| Store
    Store --> SaveMsg[Insert message:<br/>session_id, role, content]
    SaveMsg --> Wait[Wait for next message]
    Wait --> Send
    
    %% --- New Chat ---
    Send -->|New Chat clicked| Clear[Reset chatSessionRef = null<br/>Clear agent cache<br/>Reset UI state]
    Clear --> Init
```

---

## 7. Report & Revenue Flow

```mermaid
flowchart TD
    Start([Simulation complete]) --> Collect[Collect all agent decisions]
    Collect --> CalcMetrics[Calculate:<br/>total visits, revenue,<br/>churn count, visit rate]
    
    CalcMetrics --> ScenarioType{Price scenario?}
    ScenarioType -->|Yes| IncomeBreakdown[Breakdown by income:<br/>B40/M40/T20]
    ScenarioType -->|No| PersonalityBreakdown[Breakdown by personality:<br/>student/professional/etc.]
    
    IncomeBreakdown --> Risk
    PersonalityBreakdown --> Risk[Determine risk level:<br/>High >= 30% churn<br/>Medium 15-30%<br/>Low < 15%]
    
    Risk --> LLMRecs[LLM generates analysis<br/>+ 3 recommendations]
    LLMRecs --> BuildReport[Build report object]
    BuildReport --> Stream[SSE: simulation_complete]
    Stream --> SaveDB[Save to simulation_reports table]
    SaveDB --> ShowChat[Display in chat with<br/>PDF download button]
    
    %% --- Revenue Calculation ---
    ShowChat --> RevNote[Revenue note:<br/>Estimated from business price range<br/>adjusted by scenario price change]
    
    %% --- PDF ---
    ShowChat --> PDF{User clicks Download?}
    PDF -->|Yes| GenPDF[Generate PDF:<br/>risk summary, charts,<br/>breakdown, recommendations]
    GenPDF --> Filename[Filename:<br/>aria-scenario-slug-YYYY-MM-DD.pdf]
    Filename --> Download([Browser downloads PDF])
```

---

## 8. Simulation History Flow

```mermaid
flowchart TD
    Start([Dashboard mounts]) --> Load{profileId available?}
    Load -->|No| Empty[History = empty]
    Load -->|Yes| Fetch[GET /api/simulation/history/profileId]
    Fetch --> Query[Query: scenarios +<br/>simulations + reports]
    Query --> Group[Group by date:<br/>Today, Yesterday,<br/>Last 7 days, Older]
    Group --> Display[Display in HistorySidebar]
    
    Display --> Action{User action?}
    Action -->|Click item| Restore[Restore snapshot:<br/>scenario, metrics,<br/>agents, feed, influences]
    Restore --> Dashboard[Dashboard shows<br/>restored simulation]
    
    Action -->|Delete item| Confirm[Confirm deletion]
    Confirm --> Cascade[DELETE cascade:<br/>events → reports →<br/>simulation → scenario]
    Cascade --> Remove[Remove from UI]
```

---

## 9. Database Operations Flow

```mermaid
flowchart TD
    Start([API endpoint called]) --> Client[Instantiate SupabaseClient]
    Client --> Build[Build REST request:<br/>URL + params + headers]
    Build --> Headers[Headers:<br/>apikey, Authorization Bearer,<br/>Prefer: return=representation]
    Headers --> Send[aiohttp async request<br/>to Supabase REST API]
    Send --> Status{Response status?}
    Status -->|200/201| Parse[Parse JSON response]
    Parse --> Return([Return data to caller])
    Status -->|409| Conflict[FK/unique constraint violation]
    Conflict --> HandleError([Log + raise appropriate error])
    Status -->|Other| HandleError
    
    %% --- Simulation Save Sequence ---
    Return --> SaveSeq[Simulation save sequence:]
    SaveSeq --> S1[1. Save scenario<br/>profile_id, name, type, params]
    S1 --> S2[2. Save simulation<br/>scenario_id, agent_count, timestamps]
    S2 --> S3[3. Save simulation_events<br/>bulk insert decisions]
    S3 --> S4[4. Save simulation_report<br/>risk, breakdown, recommendations]
```

---

## 10. External Data Integration

```mermaid
flowchart TD
    Start([Scenario suggestion triggered]) --> Keywords{Question contains<br/>holiday/raya/school<br/>keywords?}
    
    %% --- Calendar ---
    Keywords -->|Yes| Calendar[Fetch Malaysia Calendar API<br/>holidays + school terms<br/>for Pulau Pinang]
    Keywords -->|No| SkipCal[No calendar context]
    
    %% --- News ---
    Calendar --> NewsCheck
    SkipCal --> NewsCheck{Real-world context<br/>enabled + NEWS_API_KEY set?}
    NewsCheck -->|Yes| News[Fetch newsdata.io<br/>Malaysian economic news]
    NewsCheck -->|No| SkipNews[No news context]
    
    %% --- Demographics ---
    News --> DOSM
    SkipNews --> DOSM[Load DOSM demographics<br/>for business district<br/>age + income distributions]
    
    DOSM --> Inject[Inject all context<br/>into scenario prompt]
    Inject --> Done([LLM generates<br/>context-aware scenarios])
```
