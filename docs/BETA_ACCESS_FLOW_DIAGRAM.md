# ARIA Beta Access Control - Flow Diagram

## Complete User Journey

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ADMIN ACTIONS                                   │
└─────────────────────────────────────────────────────────────────────────┘

    Admin                                                                    
      │                                                                      
      ├─→ Opens Supabase Dashboard                                         
      │   → Authentication → Users                                          
      │   → Click "Invite user"                                             
      │   → Enter: user@example.com                                         
      │   → Click "Send invitation"                                         
      │                                                                      
      └─→ Supabase sends invitation email                                  
            (Link valid for 6 hours)                                        


┌─────────────────────────────────────────────────────────────────────────┐
│                      USER RECEIVES INVITATION                           │
└─────────────────────────────────────────────────────────────────────────┘

    User Inbox                                                              
      │                                                                      
      ├─→ Receives email: "You've been invited to join ARIA"              
      │   Subject: "You're invited to join ARIA"                           
      │   Body: "Click here to join" → https://aria.app/auth/setup-password#access_token=abc123...
      │                                                                      
      └─→ User clicks link (must click within 6 hours)                    


┌─────────────────────────────────────────────────────────────────────────┐
│                     PASSWORD SETUP FLOW                                 │
└─────────────────────────────────────────────────────────────────────────┘

    Browser redirects to: /auth/setup-password                             
      │                                                                      
      ├─→ Page extracts access_token from URL fragment                    
      │   (#access_token=abc123...)                                         
      │                                                                      
      ├─→ User sees password setup form:                                  
      │   ┌─────────────────────────────────┐                              
      │   │ Set Your Password              │                              
      │   ├─────────────────────────────────┤                              
      │   │ Password: [**********]         │                              
      │   │ Confirm:  [**********]         │                              
      │   │                                │                              
      │   │ ☑ I accept Terms & Conditions  │                              
      │   │                                │                              
      │   │ [Set Password & Continue]      │                              
      │   └─────────────────────────────────┘                              
      │                                                                      
      ├─→ User fills form and submits                                     
      │                                                                      
      ├─→ Frontend sends: POST /api/auth/setup-password                   
      │   {                                                                 
      │     "access_token": "abc123...",                                   
      │     "new_password": "SecureP@ss1",                                 
      │     "accepted_terms": true                                         
      │   }                                                                 
      │                                                                      
      └─→ Backend processing:                                             
            │                                                                
            ├─→ Validate password strength                                 
            ├─→ Update password in Supabase Auth                           
            ├─→ Decode JWT to get user_id                                  
            ├─→ Call: set_beta_access_expiration(user_id, 7)              
            │   → Sets expires_at = NOW() + 7 days                         
            │   → Records invited_at = NOW()                               
            ├─→ Call: record_terms_acceptance(user_id)                    
            │   → Records accepted_terms_at = NOW()                        
            │                                                                
            └─→ Return success                                             


┌─────────────────────────────────────────────────────────────────────────┐
│                  USER METADATA (in auth.users)                          │
└─────────────────────────────────────────────────────────────────────────┘

    auth.users.raw_user_meta_data:                                         
    {                                                                       
      "beta_access_expires_at": "2026-09-30T10:35:00Z",  ← 7 days from password setup
      "beta_invited_at": "2026-09-23T10:35:00Z"          ← Password setup time
    }                                                                       


┌─────────────────────────────────────────────────────────────────────────┐
│                       USER LOGIN FLOW                                   │
└─────────────────────────────────────────────────────────────────────────┘

    User navigates to /auth/login                                          
      │                                                                      
      ├─→ Enters email + password                                         
      │                                                                      
      ├─→ Frontend sends: POST /api/auth/login                            
      │   { "email": "user@example.com", "password": "..." }              
      │                                                                      
      └─→ Backend processing:                                             
            │                                                                
            ├─→ Supabase Auth validates credentials                        
            │   ├─ Invalid? → Return 401 "Incorrect email or password"    
            │   ├─ Email not confirmed? → Return 403 "EMAIL_NOT_CONFIRMED"
            │   └─ Valid → Continue                                        
            │                                                                
            ├─→ Check beta access: is_beta_access_valid(user_id)          
            │   │                                                            
            │   ├─ Query: SELECT raw_user_meta_data FROM auth.users       
            │   ├─ Extract: expires_at from metadata                       
            │   ├─ Compare: expires_at > NOW() ?                           
            │   │                                                            
            │   ├─ TRUE → Access valid → Return JWT                        
            │   └─ FALSE → Return 403 "BETA_ACCESS_EXPIRED"               
            │                                                                
            └─→ User logged in (if valid)                                  


┌─────────────────────────────────────────────────────────────────────────┐
│                    ACTIVE SESSION (Days 1-7)                            │
└─────────────────────────────────────────────────────────────────────────┘

    User is logged in and using ARIA                                       
      │                                                                      
      ├─→ User creates business profile                                   
      ├─→ User runs simulations                                           
      ├─→ User chats with ARIA                                            
      │                                                                      
      └─→ Every API request:                                              
            │                                                                
            ├─→ JWT validated by Supabase                                  
            │                                                                
            ├─→ Database query executed                                    
            │                                                                
            └─→ RLS Policy checks:                                         
                  │                                                          
                  ├─ User owns the data? (user_id = auth.uid())           
                  ├─ Beta access valid? is_beta_access_valid(auth.uid())  
                  │                                                          
                  ├─ BOTH TRUE → Return data                              
                  └─ EITHER FALSE → Return empty result (403)             


┌─────────────────────────────────────────────────────────────────────────┐
│                     EXPIRATION DAY (Day 7)                              │
└─────────────────────────────────────────────────────────────────────────┘

    Clock strikes expires_at timestamp                                     
      │                                                                      
      ├─→ User tries to login                                             
      │     │                                                                
      │     ├─→ Credentials valid                                         
      │     ├─→ is_beta_access_valid() returns FALSE                      
      │     └─→ Backend returns: 403 "BETA_ACCESS_EXPIRED"               
      │                                                                      
      ├─→ Frontend shows:                                                 
      │   ┌─────────────────────────────────────┐                          
      │   │ ✖ Beta Access Expired               │                          
      │   │                                      │                          
      │   │ Your beta access period has expired.│                          
      │   │ Please contact the administrator to │                          
      │   │ extend your access.                 │                          
      │   └─────────────────────────────────────┘                          
      │                                                                      
      └─→ User is blocked from all access                                


┌─────────────────────────────────────────────────────────────────────────┐
│                   ADMIN EXTENDS ACCESS                                  │
└─────────────────────────────────────────────────────────────────────────┘

    Admin opens Supabase SQL Editor                                        
      │                                                                      
      ├─→ Runs: SELECT * FROM extend_beta_access('user@example.com', 7)  
      │                                                                      
      └─→ Function updates metadata:                                      
            │                                                                
            ├─→ Current expires_at: 2026-09-30                            
            ├─→ Add 7 days                                                 
            ├─→ New expires_at: 2026-10-07                                
            │                                                                
            └─→ UPDATE auth.users SET raw_user_meta_data = ...           


┌─────────────────────────────────────────────────────────────────────────┐
│                 USER CAN LOGIN AGAIN                                    │
└─────────────────────────────────────────────────────────────────────────┘

    User tries to login again                                              
      │                                                                      
      ├─→ is_beta_access_valid() returns TRUE                            
      │   (New expires_at is in the future)                               
      │                                                                      
      └─→ Login succeeds → Access restored                               


┌─────────────────────────────────────────────────────────────────────────┐
│              ALTERNATIVE: ADMIN REVOKES ACCESS                          │
└─────────────────────────────────────────────────────────────────────────┘

    Admin wants to immediately revoke access                               
      │                                                                      
      ├─→ Runs: SELECT * FROM revoke_beta_access('user@example.com')     
      │                                                                      
      └─→ Function sets expires_at = NOW()                               
            │                                                                
            └─→ User immediately blocked on next request                   


═════════════════════════════════════════════════════════════════════════
                          KEY DECISION POINTS
═════════════════════════════════════════════════════════════════════════

  ┌─────────────────────┐
  │ Invitation Link     │ ─→ Valid (< 6 hrs) ─→ Password Setup Page
  │ Clicked?            │ ─→ Expired (> 6 hrs) ─→ "Invalid Link" Page
  └─────────────────────┘

  ┌─────────────────────┐
  │ Password Setup      │ ─→ Valid ─→ Countdown Starts (7 days)
  │ Submitted?          │ ─→ Invalid ─→ Show validation errors
  └─────────────────────┘

  ┌─────────────────────┐
  │ Login Attempt       │ ─→ Credentials invalid ─→ 401 Error
  │ (any time)          │ ─→ Credentials valid ─→ Check beta access
  └─────────────────────┘           │
                                    ├─→ Valid ─→ Login success
                                    └─→ Expired ─→ 403 "BETA_ACCESS_EXPIRED"

  ┌─────────────────────┐
  │ API Request         │ ─→ JWT invalid ─→ 401 Unauthorized
  │ (any endpoint)      │ ─→ JWT valid ─→ Check RLS policies
  └─────────────────────┘           │
                                    ├─→ Beta valid + owns data ─→ Return data
                                    └─→ Beta expired or not owner ─→ Empty (403)


═════════════════════════════════════════════════════════════════════════
                         ADMIN MANAGEMENT FLOW
═════════════════════════════════════════════════════════════════════════

  View all users:
  ┌────────────────────────────────────────┐
  │ SELECT * FROM list_beta_users();       │
  └────────────────────────────────────────┘
           ↓
  ┌─────────────────────────────────────────────────────────────┐
  │ user_id | email          | expires_at | is_expired | days   │
  │ abc-123 | user@email.com | 2026-09-30 | FALSE      | 5      │
  │ def-456 | test@email.com | 2026-09-25 | TRUE       | 0      │
  └─────────────────────────────────────────────────────────────┘

  Extend access:
  ┌────────────────────────────────────────────────────────┐
  │ SELECT * FROM extend_beta_access('user@email.com', 7); │
  └────────────────────────────────────────────────────────┘
           ↓
  ┌──────────────────────────────────────────────────────────┐
  │ Old expires_at: 2026-09-30                               │
  │ New expires_at: 2026-10-07 (added 7 days)               │
  └──────────────────────────────────────────────────────────┘

  Revoke access:
  ┌───────────────────────────────────────────────────┐
  │ SELECT * FROM revoke_beta_access('user@email.com');│
  └───────────────────────────────────────────────────┘
           ↓
  ┌────────────────────────────────┐
  │ Access revoked immediately      │
  │ expires_at set to NOW()        │
  └────────────────────────────────┘


═════════════════════════════════════════════════════════════════════════
                         DATABASE FUNCTION FLOW
═════════════════════════════════════════════════════════════════════════

  is_beta_access_valid(user_id) - Called on every authenticated request
  ┌──────────────────────────────────────────────────┐
  │ 1. Query: SELECT raw_user_meta_data             │
  │           FROM auth.users WHERE id = user_id    │
  │                                                  │
  │ 2. Extract: expires_at from metadata            │
  │                                                  │
  │ 3. Compare: expires_at > NOW() ?                │
  │    ├─ TRUE → Return TRUE                        │
  │    ├─ FALSE → Return FALSE                      │
  │    └─ NULL → Return FALSE (no expiration set)   │
  └──────────────────────────────────────────────────┘

  set_beta_access_expiration(user_id, days) - Called after password setup
  ┌──────────────────────────────────────────────────┐
  │ 1. Get current metadata                          │
  │                                                  │
  │ 2. Calculate: expires_at = NOW() + days         │
  │                                                  │
  │ 3. Update metadata:                              │
  │    {                                             │
  │      "beta_access_expires_at": "2026-09-30...", │
  │      "beta_invited_at": "2026-09-23..."         │
  │    }                                             │
  │                                                  │
  │ 4. UPDATE auth.users SET ...                    │
  └──────────────────────────────────────────────────┘

  record_terms_acceptance(user_id) - Called after T&C checkbox
  ┌──────────────────────────────────────────────────┐
  │ 1. Get current metadata                          │
  │                                                  │
  │ 2. Add: "accepted_terms_at": NOW()              │
  │                                                  │
  │ 3. UPDATE auth.users SET ...                    │
  └──────────────────────────────────────────────────┘


═════════════════════════════════════════════════════════════════════════
                              TIMELINE
═════════════════════════════════════════════════════════════════════════

  Day 0, 10:00 AM  │ Admin sends invitation
                   │
  Day 0, 10:05 AM  │ User receives email
                   │
  Day 0, 10:35 AM  │ User sets password
                   │ ✓ 7-day countdown starts HERE
                   │ ✓ T&C acceptance recorded
                   │ ✓ expires_at = 2026-09-30 10:35:00
  ──────────────────
  Day 0-6          │ User actively using system
                   │ ✓ All features accessible
                   │ ✓ RLS checks passing
  ──────────────────
  Day 7, 10:34 AM  │ User still has access (1 minute remaining)
                   │
  Day 7, 10:35 AM  │ EXPIRATION! Access blocked
                   │ ✗ Login blocked
                   │ ✗ API requests return empty
                   │
  Day 7, 11:00 AM  │ Admin extends by 7 days
                   │ ✓ New expires_at = 2026-10-07 10:35:00
                   │
  Day 7, 11:01 AM  │ User can login again
  ──────────────────
  Day 8-14         │ User continues using (extended period)
                   │
  Day 14, 10:35 AM │ EXPIRATION AGAIN (if not extended)


═════════════════════════════════════════════════════════════════════════
```

## Key Characteristics

### Precise to the Second
- Access expires EXACTLY at the `expires_at` timestamp
- No grace period, no rounding
- Clock synchronization matters (uses server time)

### Database-Level Enforcement
- Every query checks `is_beta_access_valid()`
- No application-level bypass possible
- Even if JWT is valid, data access is blocked

### Zero Maintenance
- No cron jobs
- No background workers
- No scheduled tasks
- Pure database logic

### Admin Flexibility
- Extend at any time (before or after expiration)
- Revoke immediately (no waiting)
- View status in real-time
- All via simple SQL commands

## Invitation Link Lifecycle

```
Invitation Sent (t=0)
    ↓
Valid Period: 0 - 6 hours
    ↓
Expires (t=6 hours) ──→ Link becomes invalid
                        User must request new invitation
```

## Beta Access Lifecycle

```
Password Set (t=0) ─────→ 7-day countdown starts
    ↓
Active Period: Day 0 - Day 7
    ↓
Expires (t=7 days) ─────→ Access blocked
                          Admin can extend
```

---

This diagram shows the complete flow from invitation to expiration, including all decision points, database operations, and admin management actions.
