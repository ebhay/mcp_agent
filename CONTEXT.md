# TrainMate &bull; System Context & Architecture Guide

> **TrainMate** is an enterprise-grade web application engineered to automate technical training cohort management and trainer allocation within corporate academies (designed for **Cognizant Digital Academy**).

---

## 1. Executive Summary & Purpose

In large-scale enterprise training organizations, managing hundreds of technical training batches (**cohorts**) simultaneously is a complex operational challenge. Academic coaches frequently face the burden of manually reviewing trainer availability, calculating skill alignment, checking workload limits, and communicating schedule confirmations.

**TrainMate replaces error-prone, manual spreadsheets with a deterministic, full-stack automated allocation platform.** 

It empowers **Coaches** to create cohorts individually or batch-upload them via Excel, while an intelligent **100-Point Allocation Engine** automatically identifies, scores, and assigns the best-suited trainer in real time without human bias or double-booking. **Administrators** maintain global governance, workload balancing controls, and one-click reassignment capabilities, while **Trainers** get immediate visibility into their teaching schedules and internal mailbox alerts.

```
+---------------------------------------------------------------------------------------+
|                                    TRAINMATE SYSTEM                                   |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|   +-------------------+        +--------------------+        +--------------------+   |
|   |    COACH PORTAL   |        |   TRAINER PORTAL   |        |    ADMIN CONSOLE   |   |
|   | - Create Cohorts  |        | - View Schedules   |        | - System Analytics |   |
|   | - Excel Batch Up. |        | - Active Batches   |        | - Capacity Tuning  |   |
|   | - Track Delivery  |        | - Internal Mailbox |        | - Manual Overrides |   |
|   +---------+---------+        +---------+----------+        +---------+----------+   |
|             |                            |                             |              |
|             +----------------------------+-----------------------------+              |
|                                          |                                            |
|                                          v                                            |
|                        +----------------------------------+                           |
|                        |   Angular 19 Standalone Client   |                           |
|                        +-----------------+----------------+                           |
|                                          | REST API (JSON)                            |
|                                          v                                            |
|                        +----------------------------------+                           |
|                        |  Spring Boot 3.3.5 (Java 21) MVC |                           |
|                        |                                  |                           |
|                        |   * 100-Point Allocation Engine  |                           |
|                        |   * Pessimistic / Optimistic Lock|                           |
|                        |   * Apache POI Excel Processor   |                           |
|                        |   * Internal Mail Dispatcher     |                           |
|                        +-----------------+----------------+                           |
|                                          | Spring Data JPA / Hibernate                |
|                                          v                                            |
|                        +----------------------------------+                           |
|                        |      MySQL 8.0 (4 Core Tables)   |                           |
|                        |   users | trainer | cohort | mail|                           |
|                        +----------------------------------+                           |
+---------------------------------------------------------------------------------------+
```

---

## 2. Business Problem & Solution

### The Operational Challenge
Before TrainMate, managing corporate training pipelines presented several acute friction points:
1. **Spreadsheet Chaos**: Cohort requirements and trainer availability were tracked in disparate Excel sheets, leading to version confusion and lost requests.
2. **Double Booking & Overload**: Without centralized concurrency control, popular trainers were inadvertently assigned to overlapping batches, leading to trainer burnout and dropped quality.
3. **Skill Mismatches**: Assigning trainers based on subjective familiarity rather than objective skill matching resulted in sub-optimal learning outcomes for trainees.
4. **Communication Lag**: When batch dates changed or trainer overrides were executed, stakeholders were rarely notified in a timely manner.

### The TrainMate Solution
- **Automated 100-Point Scoring**: Evaluates candidate trainers across 5 objective criteria (skills, availability, workload, experience, track record).
- **Dual Creation Channels**: Coaches can use an intuitive reactive web form for single cohorts or upload an entire schedule via a validated Excel (`.xlsx`) sheet.
- **Race-Condition Free**: Database-level pessimistic and optimistic locking prevents concurrent allocations and double-booking.
- **Explainable Decisions**: Every automatic allocation generates a plain-language explanation and numeric breakdown stored with the cohort.
- **Internal Messaging (Mailbox)**: Automated internal mails are dispatched instantaneously to Coaches, Trainers, and Admins whenever assignments, reassignments, or unassigned alerts occur.

---

## 3. User Personas & Core Workflows

TrainMate implements Role-Based Access Control (**RBAC**) across three dedicated personas:

```
               [ User Authentication: Login (/api/auth/login) ]
                                      |
            +-------------------------+-------------------------+
            |                         |                         |
       Role: COACH              Role: TRAINER              Role: ADMIN
            |                         |                         |
            v                         v                         v
   - Coach Dashboard         - Trainer Dashboard       - Admin Master Dashboard
   - Single Cohort Form      - Assigned Batches List   - Global Cohort Directory
   - Excel Batch Upload      - Upcoming Schedules      - Trainer Capacity Mgmt
   - Real-time Allocation    - Training Mailbox        - Manual Override Engine
   - Cohort Delivery List    - Workload Ratios         - Excel Report Export
```

### 1. The Coach (`Role.COACH`)
- **Role**: Academic managers responsible for planning and delivering technical curricula to trainee batches.
- **Key Capabilities**:
  - **Single Cohort Ingestion**: Creates batches specifying stream, service line (e.g. QEA, Digital Engineering), vertical (Healthcare, Banking), required skills, trainee count, and dates.
  - **Excel Batch Ingestion**: Uploads multi-row `.xlsx` sheets with comprehensive row-by-row validation.
  - **Instant Auto-Allocation**: Triggers the scoring engine upon creation; immediately sees who was assigned and why.
  - **Cohort Tracking**: Monitors cohort statuses (`PENDING`, `ASSIGNED`, `UNASSIGNED`, `ACTIVE`, `COMPLETED`, `CANCELLED`).
  - **1-Click Reallocation**: If a trainer becomes unavailable, the coach can re-run the allocation engine with one click.

### 2. The Trainer (`Role.TRAINER`)
- **Role**: Technical instructors delivering courses on modern tech stacks (Java, Spring Boot, Angular, Cloud, Microservices).
- **Key Capabilities**:
  - **Schedule Visibility**: Views assigned cohorts sorted chronologically by start date.
  - **Workload Awareness**: Tracks their current workload vs. maximum allowed capacity (e.g., `2/5` active batches).
  - **Personal Mailbox**: Receives automated notices when assigned to a new batch or unassigned by an admin override.
  - **Batch Detail Inspection**: Inspects trainee headcounts, locations, curriculum requirements, and start/end dates.

### 3. The Administrator (`Role.ADMIN`)
- **Role**: Academy leadership with global oversight and operational governance.
- **Key Capabilities**:
  - **Executive KPI Dashboard**: Monitors platform-wide cohort distributions, available vs. unavailable trainers, and unassigned alerts.
  - **Trainer Capacity Balancing**: Registers new trainers, adjusts maximum workload ceilings, updates technical skill tags, and toggles trainer availability.
  - **Administrative Override**: Manually reassigns any cohort to a specific trainer with mandatory recorded justification, automatically adjusting workloads and notifying all parties.
  - **Bulk Operations**: Executes batch deletion of cohorts and trainers with atomic set-based SQL queries.
  - **Enterprise Reporting**: One-click download of the complete platform allocation matrix in formatted Excel (`.xlsx`) format.

---

## 4. The 100-Point Allocation Engine

The centerpiece of TrainMate is the deterministic allocation algorithm implemented in `AllocationScorer` and `TrainerAllocationService`.

### Step 1: Strict Eligibility Gates (Hard Filters)
Before any score is computed, a trainer must pass three non-negotiable gates:
1. **Workload Gate**: `currentWorkload < maxWorkload` (trainers at full capacity are disqualified).
2. **Availability Window**: `availableFrom <= cohort.startDate` AND `availableTill >= cohort.endDate`.
3. **Skill Intersection**: Trainer's skill set must match at least **one** required skill from the cohort.

If any gate fails, the trainer is marked `ineligible` with a specific recorded reason.

### Step 2: Weighted Scoring Matrix (Up to 100 Points)

| Dimension | Max Points | Weight | Formula & Evaluation Logic |
| :--- | :---: | :---: | :--- |
| **Skill Match** | **40 pts** | 40% | $\frac{\text{Matched Skills Count}}{\text{Total Required Skills}} \times 40.0$<br>Evaluates exact token matches against comma-separated skill tags. |
| **Availability** | **20 pts** | 20% | **20.0 pts** awarded if availability dates fully encompass the batch; 0 otherwise. |
| **Workload Headroom** | **15 pts** | 15% | $\frac{\text{maxWorkload} - \text{currentWorkload}}{\text{maxWorkload}} \times 15.0$<br>Favors trainers with lower current commitments to balance academy load. |
| **Seniority & Experience**| **15 pts** | 15% | &bull; $\le 2$ years: **5.0 pts**<br>&bull; $3 - 5$ years: **10.0 pts**<br>&bull; $> 5$ years: **15.0 pts** |
| **Past Track Record** | **10 pts** | 10% | Evaluates previously delivered completed batches:<br>&bull; $0$ completed: **3.0 pts**<br>&bull; $1 - 2$ completed: **5.0 pts**<br>&bull; $3 - 5$ completed: **8.0 pts**<br>&bull; $> 5$ completed: **10.0 pts** |

### Step 3: Candidate Selection & Tiebreaking
1. All eligible trainers are ranked descending by **Total Score**.
2. If two trainers tie on score, the candidate with the **lower current workload** is selected.
3. The candidate is locked via pessimistic locking (`SELECT ... FOR UPDATE`), their workload is incremented (`currentWorkload + 1`), the cohort status moves to `ASSIGNED`, and an internal notification is logged.
4. If no eligible trainers exist, the cohort moves to `UNASSIGNED`, and alerts are dispatched to the Coach and all Admins for manual intervention.

### Step 4: Batch Allocation Engine (FIFO Dynamic Balancing)
For multi-row Excel uploads, the batch engine processes cohorts in strict **First-In, First-Out (FIFO)** order. When candidate $T$ wins cohort $C_1$, $T$'s workload increments in-memory immediately, ensuring that when cohort $C_2$ is evaluated, $T$'s workload score reflects the new assignment. This prevents batch uploads from over-allocating the top-ranked trainer.

---

## 5. Database Architecture (4 Core Relational Tables)

TrainMate is built upon an intentional, strictly normalized 4-table relational architecture in MySQL:

```
+---------------------------------------+           +---------------------------------------+
|                 USERS                 |           |                TRAINER                |
+---------------------------------------+           +---------------------------------------+
| PK  user_id            BIGINT         |<----+     | PK  trainer_id        BIGINT          |
|     name               VARCHAR(100)   |     +-----| FK  user_id           BIGINT (UNIQUE) |
|     email              VARCHAR(150)   |           |     skill_set         VARCHAR(500)    |
|     password           VARCHAR(255)   |           |     experience_years  DECIMAL(4,1)    |
|     role               ENUM(COACH...) |           |     available_from    DATE            |
|     version            BIGINT (OptLock|           |     available_till    DATE            |
|     created_date       TIMESTAMP      |           |     current_workload  INT             |
|     updated_date       TIMESTAMP      |           |     max_workload      INT             |
+---------------------------------------+           |     version           BIGINT          |
                   ^                                +---------------------------------------+
                   |                                                    ^
                   |                                                    |
+------------------+--------------------+-------------------------------+-------------------+
|                                       COHORT                                              |
+-------------------------------------------------------------------------------------------+
| PK  cohort_id                  BIGINT                                                     |
|     cohort_code                VARCHAR(30) (UNIQUE)                                       |
|     service_line               VARCHAR(100)                                               |
|     stream                     VARCHAR(100)                                               |
|     required_skill             VARCHAR(300)                                               |
|     trainee_count              INT                                                        |
|     start_date                 DATE                                                       |
|     end_date                   DATE                                                       |
|     location                   VARCHAR(100)                                               |
|     vertical                   VARCHAR(100)                                               |
| FK  coach_user_id              BIGINT -> users(user_id)                                   |
| FK  assigned_trainer_id        BIGINT -> trainer(trainer_id) [NULLABLE]                    |
|     status                     ENUM('PENDING','ASSIGNED','UNASSIGNED','ACTIVE',...)       |
|     allocation_score           DOUBLE                                                     |
|     allocation_explanation     VARCHAR(1000)                                              |
|     allocation_type            VARCHAR(30) ('AUTOMATIC', 'MANUAL_OVERRIDE')               |
|     allocation_date            TIMESTAMP                                                  |
|     version                    BIGINT (OptLock)                                           |
|     created_date, updated_date TIMESTAMP                                                  |
+-------------------------------------------------------------------------------------------+
                   ^
                   |
+------------------+------------------------------------------------------------------------+
|                                    NOTIFICATION (MAILBOX)                                 |
+-------------------------------------------------------------------------------------------+
| PK  notification_id            BIGINT                                                     |
| FK  cohort_id                  BIGINT -> cohort(cohort_id) [NULLABLE]                     |
| FK  receiver_user_id           BIGINT -> users(user_id)                                   |
|     notification_type          VARCHAR(50) ('COHORT_ASSIGNMENT', 'TRAINER_ASSIGNED', ...) |
|     message                    VARCHAR(500)                                               |
|     is_read                    BOOLEAN (DEFAULT FALSE)                                    |
|     created_date               TIMESTAMP                                                  |
+-------------------------------------------------------------------------------------------+
```

### Table Roles:
1. **`users`**: Root user entity supporting BCrypt authentication and role differentiation (`COACH`, `TRAINER`, `ADMIN`).
2. **`trainer`**: Specialized profile linked 1:1 to a user. Maintains availability dates, skill set strings, and capacity counters.
3. **`cohort`**: Central entity representing a training batch. Stores curriculum details, timing, assignments, and audit scores.
4. **`notification`**: Asynchronous notification log supporting unread badges and zero-overhead internal mail delivery.

---

## 6. Full Technology Stack

### Frontend Architecture
- **Framework**: **Angular 19** (Standalone Components, no legacy NgModules)
- **State & Reactivity**: RxJS 7.8, Signals, Debounced Search Inputs, Reactive Forms
- **UI & Layout**: Custom CSS3 design system, Bootstrap 5 grid, Bootstrap Icons
- **Performance & UX**:
  - Route guards (`AuthGuard`, `RoleGuard`)
  - HTTP In-Memory Caching (`HttpCacheService`) with automated cache invalidation on mutations
  - Skeleton Shimmer loading states
  - Render Cloud Cold-Start detector banner (`isColdStarting`) with automatic retry handling
- **Hosting**: Vercel configuration (`vercel.json`) with client-side SPA route rewrites

### Backend Architecture
- **Framework**: **Spring Boot 3.3.5** running on **Java 21**
- **Persistence**: Spring Data JPA / Hibernate ORM with HikariCP connection pool
- **Database**: MySQL 8.0 / Aiven Cloud Managed MySQL
- **Excel Ingestion & Export**: **Apache POI 5.2.5** (`poi-ooxml`)
- **Schema Management**: Flyway database migrations (`V1` through `V4`)
- **API Documentation**: SpringDoc OpenAPI 3.0 with interactive Swagger UI
- **Observability**: Spring Boot Actuator (`/actuator/health`, `/actuator/metrics`)
- **Hosting**: Render Cloud Platform (`https://trainmate-o6tv.onrender.com`)

---

## 7. Key Enterprise Engineering Features

1. **High-Performance Statement Batching**:
   - `spring.jpa.properties.hibernate.jdbc.batch_size=50`
   - MySQL `rewriteBatchedStatements=true`
   - O(1) set-based bulk deletion and bulk unassignment queries instead of iterative loops.
2. **Dual-Tier Concurrency Control**:
   - **Pessimistic Locking** (`SELECT ... FOR UPDATE` via `findByIdForUpdate`): Used during real-time trainer allocation and reassignments to prevent race conditions.
   - **Optimistic Locking** (`@Version Long version`): Implemented across `User`, `Trainer`, and `Cohort` to catch concurrent modifications gracefully.
3. **Dual URL Route Mapping**:
   - Every REST controller is mapped to both `/api/*` and bare paths (e.g. `@RequestMapping({"/api/admin", "/admin"})`), ensuring full backward compatibility across frontend environments.
4. **Excel Template & Auto-Sizing**:
   - Dynamic template generation (`GET /api/cohorts/sample-template`) with styled header cells and sample rows matching business requirements.
5. **Cold-Start Resilience**:
   - Dedicated lightweight `/api/health/live` probe allows frontend pre-warming when hosted on cloud free-tier containers without putting load on the database.

---

## 8. Demo Credentials & Test Accounts

The login interface features quick test buttons and supports:

| Role | Username / Email | Password | Primary Functions |
| :--- | :--- | :--- | :--- |
| **Coach** | `coach01` or `coach01@cognizant.com` | `password123` *(or `coach123`)* | Create cohorts, upload Excel sheets, monitor allocations |
| **Trainer** | `trainer01` or `trainer01@cognizant.com` | `password123` *(or `trainer123`)* | View assigned batches, inspect curriculum, read incoming mail |
| **Admin** | `admin01` or `admin01@cognizant.com` | `password123` *(or `admin123`)* | Global analytics, capacity tuning, manual overrides, Excel exports |

---

## 9. Related Documentation Links
- **Full REST API Specification**: [EndPoints.md](file:///c:/Users/workf/Desktop/Development/EndPoints.md)
- **Project Readme**: [README.md](file:///c:/Users/workf/Desktop/Development/TrainMate/README.md)
- **Database Schema**: [schema.sql](file:///c:/Users/workf/Desktop/Development/TrainMate/database/schema.sql)
