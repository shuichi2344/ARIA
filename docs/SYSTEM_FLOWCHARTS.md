# ARIA System Flow Charts

> Detailed flow diagrams for each major module in the ARIA platform.

---

## 1. Account Module Flow

```mermaid
flowchart TD
    Start([Start]) --> A{User logged in?}
    A -->|Yes| Dashboard[/View Dashboard/]
    A -->|No| B{Has existing account?}
    
    %% --- Login Path ---
    B -->|Yes| C[/Enter Login Details<br/>email + password/]
    C --> D{Correct credentials?}
    D -->|Yes| E{Has business profile?}
    E -->|Yes| Dashboard
    E -->|No| Onboarding[Redirect to Onboarding]
    D -->|No| F{Forgot password?}
    F -->|No| C
    
    %% --- Forgot Password Path ---
    F -->|Yes| G[/Enter email address/]
    G --> H{Valid email?}
    H -->|No| G
    H -->|Yes| I[/Password reset email sent<br/>or link printed to console in dev/]
    I --> J[/User clicks email link/]
    J --> K[/View Reset Password page/]
    K --> L[/Enter new password/]
    L --> M{Valid password?<br/>6+ chars, uppercase,<br/>number, special char}
    M -->|No| L
    M -->|Yes| N[/Account password updated<br/>User closes tab/]
    N --> C
    
    %% --- Registration Path ---
    B -->|No| O[/Enter account details<br/>email + password/]
    O --> P{Valid email and<br/>strong password?}
    P -->|No| O
    P -->|Yes| Q{Email linked to<br/>existing account?}
    Q -->|Yes| R[/Prompt user to<br/>login instead/]
    R --> C
    Q -->|No| S[Account created]
    S --> Onboarding
    
    %% --- Change Password (from Dashboard) ---
    Dashboard --> T{Change password?}
    T -->|No| End([End])
    T -->|Yes| U[/Enter current password<br/>+ new password/]
    U --> V{Current password correct<br/>AND new password valid?}
    V -->|No| U
    V -->|Yes| W[/Password updated/]
    W --> Dashboard
```

---

## 2. Onboarding Module Flow

```mermaid
flowchart TD
    Start([Start]) --> S1[/Enter Business Info<br/>name, type, category,<br/>years operating, USPs/]
    S1 --> S2[/Enter Location<br/>state, district, city/]
    S2 --> S3[Request AI Analysis]
    
    S3 --> LLM[POST /api/business/analyze<br/>rate limited: 15/min]
    LLM --> Build[Build prompt with<br/>business name, type,<br/>location, USPs]
    Build --> Call[LLMClient.generate<br/>Ilmu AI nemo-super / Ollama fallback]
    Call --> Parse{Valid JSON response?}
    Parse -->|No| Retry{Retries left?}
    Retry -->|Yes| Call
    Retry -->|No| Error[/Show error message/]
    Error --> End([End])
    Parse -->|Yes| Display[/Display AI-generated profile:<br/>customer type B2C/B2B/HYBRID,<br/>target customers, income levels,<br/>price ranges, transaction patterns/]
    
    Display --> S4[/Review all info/]
    S4 --> Confirm{User confirms?}
    Confirm -->|Edit| S1
    Confirm -->|Yes| Save[POST /api/business/profile<br/>Save to database]
    Save --> Done[/Redirect to Dashboard/]
    Done --> End([End])
```

---

## 3. Simulation Flow (End-to-End)

```mermaid
flowchart TD
    Start([Start]) --> Question[/User types question<br/>in ChatPanel/]
    Question --> Suggest[POST /api/simulation/suggest<br/>rate limited: 15/min]
    
    %% --- Scenario Generation ---
    Suggest --> Context{Real-world<br/>context enabled?}
    Context -->|Yes| Fetch[Fetch News API +<br/>DOSM data + Calendar]
    Context -->|No| Skip[Skip external context]
    Fetch --> BuildPrompt
    Skip --> BuildPrompt[Build prompt with<br/>business profile + context]
    BuildPrompt --> GenScenarios[LLM generates 2-5 scenarios<br/>via Ilmu AI / Ollama]
    GenScenarios --> ShowScenarios[/Display scenarios to user/]
    
    %% --- Simulation Start ---
    ShowScenarios --> Select[/User selects scenario<br/>+ configures settings/]
    Select --> StartSim[POST /api/simulation/start<br/>rate limited: 10/min]
    
    %% --- Agent Generation ---
    StartSim --> Cache{Agent cache hit?<br/>same profile + constraints}
    Cache -->|Yes| Reuse[Reuse cached agents<br/>reset per-sim state]
    Cache -->|No| Generate[Generate synthetic population<br/>via IPF + DOSM data]
    Generate --> Profiles[LLM generates personality<br/>profiles in batches of 3]
    Profiles --> CacheStore[Store in agent cache<br/>keyed by profile + constraints]
    CacheStore --> CreateMesa[Create Mesa model + agents<br/>+ income-weighted social network]
    Reuse --> CreateMesa
    
    %% --- Simulation Execution (Single Pass) ---
    CreateMesa --> SSE[Open SSE stream to frontend]
    SSE --> Phase1[Phase 1: Independent Decisions<br/>Each agent decides visit/skip/churn<br/>using LLM brain]
    Phase1 --> Phase2[Phase 2: Peer Influence<br/>Gate check + LLM reconsideration<br/>for susceptible agents]
    Phase2 --> Metrics[Aggregate final metrics]
    Metrics --> Report[Generate report:<br/>risk level, breakdown,<br/>LLM analysis + recommendations]
    
    %% --- Output ---
    Report --> SaveDB[Save to database]
    SaveDB --> Display[/Display report in chat<br/>+ PDF download option/]
    Display --> End([End])
```

---

## 4. Population Generation Flow (IPF)

```mermaid
flowchart TD
    Start([Start]) --> Type{Customer type?}
    
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
    
    Type -->|B2B| B2BGen[Generate business agents<br/>from b2b_profile data<br/>sizes: Micro/Small/Medium<br/>+ target business types]
    B2BGen --> Attributes
    
    Type -->|HYBRID| Split[Split by b2b_percentage<br/>e.g. 50% B2B, 50% B2C]
    Split --> B2BGen
    Split --> DOSM
    
    Attributes --> End([End])
```

---

## 5. LLM Integration Flow (Ilmu AI + Ollama Failover)

```mermaid
flowchart TD
    Start([Start]) --> Check{ILMU_API_KEY<br/>configured?}
    
    %% --- Ilmu AI Path ---
    Check -->|Yes| Ilmu[Try Ilmu AI<br/>POST api.ilmu.ai/v1/chat/completions<br/>model: nemo-super]
    Ilmu --> IlmuOK{Success?}
    IlmuOK -->|Yes| ReturnIlmu[/Return response<br/>provider: ilmu/]
    ReturnIlmu --> End([End])
    IlmuOK -->|No| IlmuRetry{Retries left?<br/>max 3 attempts}
    IlmuRetry -->|Yes| IlmuWait[Wait with backoff] --> Ilmu
    IlmuRetry -->|No| LogWarn[Log: Ilmu failed,<br/>falling back to Ollama]
    
    %% --- Ollama Fallback ---
    Check -->|No| Ollama
    LogWarn --> Ollama[Try Ollama<br/>POST localhost:11434/api/generate<br/>model: qwen2.5:7b]
    Ollama --> OllamaOK{Success?}
    OllamaOK -->|Yes| ReturnOllama[/Return response<br/>provider: ollama/]
    ReturnOllama --> End
    OllamaOK -->|No| OllamaRetry{Retries left?<br/>max 3 attempts}
    OllamaRetry -->|Yes| OllamaWait[Wait with backoff] --> Ollama
    OllamaRetry -->|No| Fail[/Raise LLMClientError:<br/>All providers failed/]
    Fail --> End
```

---

## 6. Chat & Session Flow

```mermaid
flowchart TD
    Start([Start]) --> Init[chatSessionRef = null]
    Init --> Send{User sends message?}
    Send -->|Yes| Input[/User types message/]
    Input --> Display[/Display in UI/]
    Display --> Persist[POST /api/chat/message]
    Persist --> HasSession{session_id exists?}
    HasSession -->|No| Create[Create new chat_session<br/>in database]
    Create --> Store[Store session_id in ref]
    HasSession -->|Yes| Store
    Store --> SaveMsg[Insert message:<br/>session_id, role, content]
    SaveMsg --> Wait{More messages?}
    Wait -->|Yes| Send
    Wait -->|No| End([End])
    
    %% --- New Chat ---
    Send -->|New Chat clicked| Clear[Reset chatSessionRef = null<br/>POST /api/simulation/cache/clear<br/>Reset UI state]
    Clear --> Init
```

---

## 7. Report & Revenue Flow

```mermaid
flowchart TD
    Start([Start]) --> Collect[Collect all agent decisions]
    Collect --> CalcMetrics[Calculate:<br/>total visits, revenue,<br/>churn count, visit rate]
    
    CalcMetrics --> ScenarioType{Price scenario?}
    ScenarioType -->|Yes| IncomeBreakdown[Breakdown by income/size:<br/>B40/M40/T20 or Micro/Small/Medium]
    ScenarioType -->|No| PersonalityBreakdown[Breakdown by personality:<br/>student/professional/foodie/etc.]
    
    IncomeBreakdown --> Risk
    PersonalityBreakdown --> Risk{Risk level?}
    Risk -->|churn >= 30%| High[Risk: High]
    Risk -->|churn 15-30%| Medium[Risk: Medium]
    Risk -->|churn < 15%| Low[Risk: Low]
    High --> LLMRecs
    Medium --> LLMRecs
    Low --> LLMRecs[LLM generates analysis<br/>+ 3 recommendations]
    LLMRecs --> BuildReport[Build report object]
    BuildReport --> Stream[SSE: simulation_complete]
    Stream --> SaveDB[Save to simulation_reports table]
    SaveDB --> ShowChat[/Display report in chat/]
    
    ShowChat --> PDF{User clicks Download?}
    PDF -->|No| End([End])
    PDF -->|Yes| GenPDF[Generate PDF:<br/>risk summary, revenue disclaimer,<br/>stacked bar chart,<br/>breakdown, recommendations]
    GenPDF --> Filename[Filename:<br/>aria-scenario-slug-YYYY-MM-DD.pdf]
    Filename --> Download[/Browser downloads PDF/]
    Download --> End
```

---

## 8. Simulation History Flow

```mermaid
flowchart TD
    Start([Start]) --> Load{profileId available?}
    Load -->|No| Empty[/Show empty history/]
    Empty --> End([End])
    Load -->|Yes| Fetch[GET /api/simulation/history/profileId]
    Fetch --> Query[Query: scenarios +<br/>simulations + reports]
    Query --> Group[Group by date:<br/>Today, Yesterday,<br/>Last 7 days, Older]
    Group --> Display[/Display in HistorySidebar<br/>date + revenue/]
    
    Display --> Action{User action?}
    Action -->|Click item| Restore[Restore snapshot:<br/>scenario, metrics,<br/>agents, feed, influences]
    Restore --> Dashboard[/Dashboard shows<br/>restored simulation/]
    Dashboard --> End
    
    Action -->|Delete item| Confirm{Confirm deletion?}
    Confirm -->|No| Display
    Confirm -->|Yes| Cascade[DELETE cascade:<br/>events, reports,<br/>simulation, scenario]
    Cascade --> Remove[Remove from UI]
    Remove --> Display
    
    Action -->|No action| End
```

---

## 9. Database Operations Flow

```mermaid
flowchart TD
    Start([Start]) --> RateLimit{Rate limit check<br/>via slowapi}
    RateLimit -->|Exceeded| Block[/429 Too Many Requests<br/>Retry-After header/]
    Block --> End([End])
    RateLimit -->|OK| Validate{Pydantic validation:<br/>extra=forbid,<br/>max_length, type checks}
    Validate -->|Invalid| Reject[/400 Bad Request<br/>with error detail/]
    Reject --> End
    Validate -->|Valid| Client[Instantiate SupabaseClient]
    Client --> Build[Build REST request:<br/>URL + params + headers]
    Build --> Send[aiohttp async request<br/>to Supabase REST API]
    Send --> Status{Response status?}
    Status -->|200/201| Parse[Parse JSON response]
    Parse --> Return[/Return data to caller/]
    Return --> End
    Status -->|409| Conflict[FK/unique constraint violation]
    Conflict --> HandleError[/Log + raise error/]
    HandleError --> End
    Status -->|Other| HandleError
```

---

## 10. External Data Integration

```mermaid
flowchart TD
    Start([Start]) --> Keywords{Question contains<br/>holiday/raya/school<br/>keywords?}
    
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
    Inject --> Done[/LLM generates<br/>context-aware scenarios/]
    Done --> End([End])
```

---

## 11. Security Flow

```mermaid
flowchart TD
    Start([Start]) --> Headers[SecurityHeadersMiddleware<br/>adds X-Content-Type-Options,<br/>X-Frame-Options, X-XSS-Protection,<br/>Referrer-Policy, Permissions-Policy]
    Headers --> CORS{CORS check<br/>Origin in allowed list?}
    CORS -->|No| Reject[/403 Forbidden/]
    Reject --> End([End])
    CORS -->|Yes| RateLimit{Rate limit check<br/>per IP via slowapi}
    RateLimit -->|Exceeded| TooMany[/429 Too Many Requests/]
    TooMany --> End
    RateLimit -->|OK| Validate{Pydantic validation:<br/>extra=forbid,<br/>max_length, type checks,<br/>email format, UUID format}
    Validate -->|Invalid| BadReq[/400 Bad Request/]
    BadReq --> End
    Validate -->|Valid| Sanitize[Sanitize inputs:<br/>strip null bytes,<br/>check injection patterns,<br/>truncate to max length]
    Sanitize -->|Suspicious| BadReq
    Sanitize -->|Clean| Auth{Auth required?}
    Auth -->|Password endpoint| PwCheck{Password strong?<br/>6+ chars, uppercase,<br/>number, special char}
    Auth -->|Other| Process[Process request]
    PwCheck -->|Weak| BadReq
    PwCheck -->|Strong| Process
    Process --> Response[/Return response<br/>with security headers/]
    Response --> End
```
