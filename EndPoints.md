# TrainMate API Specification & Endpoints Reference

This document provides the complete technical specification for all REST API endpoints available in the **TrainMate** Spring Boot backend (`trainmate-backend`). It covers URL routes, HTTP methods, headers, path & query parameters, request schemas, response formats, and error structures.

---

## 1. General Overview & Configuration

### Base URLs
- **Local Development**: `http://localhost:8080` (or `http://localhost:8081`)
- **Production Server**: `https://trainmate-o6tv.onrender.com` (or configured cloud host)
- **API Dual Prefix Routing**: All controllers support dual route mapping: with `/api` prefix (e.g., `/api/admin/...`) and without (e.g., `/admin/...`).

### Common Request Headers
| Header | Value | Description |
| :--- | :--- | :--- |
| `Content-Type` | `application/json` | Required for all `POST`, `PUT`, `PATCH` endpoints with JSON bodies |
| `Accept` | `application/json` | Expected response representation |
| `Content-Type` | `multipart/form-data` | Required for Excel cohort file upload (`POST /api/coach/{coachId}/cohorts/upload`) |

### Standard Response Envelope (`ApiResponse<T>`)
Every JSON endpoint returns a consistent JSON envelope:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": { ... },
  "errors": []
}
```

#### Field Definitions
- **`success`** (`boolean`): Indicates whether the API call succeeded (`true`) or failed (`false`).
- **`message`** (`string`): Human-readable status message or primary error summary.
- **`data`** (`object` | `array` | `primitive` | `null`): The payload returned on success.
- **`errors`** (`string[]`): Detailed validation or operational errors if `success` is `false`.

### Standard Error Structure
When validation fails or an exception is caught:

```json
{
  "success": false,
  "message": "Validation failed",
  "data": null,
  "errors": [
    "cohortCode: Cohort code is required",
    "numberOfTrainees: Number of trainees must be at least 1"
  ]
}
```

### HTTP Status Codes
| HTTP Code | Reason | Description |
| :--- | :--- | :--- |
| `200 OK` | Success | Request succeeded and response data is returned |
| `400 BAD REQUEST` | Client Error | Validation failure, bad date range, invalid file format, or ineligible trainer |
| `401 UNAUTHORIZED` | Authentication Failure | Invalid username/email or password |
| `404 NOT FOUND` | Resource Missing | Cohort, Trainer, or User ID does not exist |
| `409 CONFLICT` | Conflict | Duplicate cohort code, or optimistic locking collision |
| `405 METHOD NOT ALLOWED` | Method Not Allowed | Request used an unsupported HTTP verb |
| `500 INTERNAL SERVER ERROR` | Server Error | Unhandled server error with tracked incident ID |
| `503 SERVICE UNAVAILABLE` | Service Degraded | Database connectivity check failed during readiness probe |

---

## 2. Allocation Engine Scoring Weights (100-Point Rule)

The automatic allocation engine (`TrainerAllocationService` & `AllocationScorer`) deterministic rules:

| Criterion | Max Points | Evaluation Rules |
| :--- | :---: | :--- |
| **Skill Match** | **40 pts** | `(matchedSkills / requiredSkillsCount) * 40.0` (Trainer must match $\ge 1$ skill to be eligible) |
| **Availability** | **20 pts** | **20 pts** if `availableFrom <= startDate` AND `availableTill >= endDate`; otherwise ineligible (0 pts) |
| **Current Workload** | **15 pts** | `((maxWorkload - currentWorkload) / maxWorkload) * 15.0`. Ineligible if `currentWorkload >= maxWorkload` |
| **Experience** | **15 pts** | $\le 2$ years: **5 pts** \| $3 - 5$ years: **10 pts** \| $> 5$ years: **15 pts** |
| **Previous Cohorts** | **10 pts** | $0$ completed: **3 pts** \| $1 - 2$: **5 pts** \| $3 - 5$: **8 pts** \| $> 5$: **10 pts** |

---

## 3. Endpoints Directory

- [1. Authentication](#1-authentication)
  - `POST /api/auth/login` - User Login
- [2. Health & System Checks](#2-health--system-checks)
  - `GET /api/health` / `GET /api/health/live` - Process Liveness Probe
  - `GET /api/health/ready` - Database Readiness Probe
- [3. Coach Operations](#3-coach-operations)
  - `GET /api/coach/{coachId}/dashboard` - Coach Dashboard Counters
  - `GET /api/coach/{coachId}/cohorts` - Get All Cohorts for Coach
  - `GET /api/coach/{coachId}/cohorts/paged` - Get Filtered Paged Cohorts for Coach
  - `POST /api/coach/{coachId}/cohorts` - Create Cohort & Auto-Allocate
  - `POST /api/coach/{coachId}/cohorts/upload` - Batch Upload Cohorts via Excel
- [4. Cohort Management](#4-cohort-management)
  - `GET /api/cohorts/{cohortId}` - Get Cohort Details by ID
  - `PUT /api/cohorts/{cohortId}` - Update Cohort Details
  - `PATCH /api/cohorts/{cohortId}/status` - Update Cohort Lifecycle Status
  - `POST /api/cohorts/{cohortId}/reallocate` - Trigger 1-Click Reallocation Engine
  - `DELETE /api/cohorts/{cohortId}` - Delete Cohort & Release Trainer
  - `POST /api/cohorts/bulk-delete` - Batch Bulk Delete Cohorts
  - `GET /api/cohorts/sample-template` - Download Cohort Excel Template
- [5. Trainer Operations](#5-trainer-operations)
  - `GET /api/trainers/{trainerId}/dashboard` - Trainer Dashboard Counters
  - `GET /api/trainers/{trainerId}/cohorts` - Get All Assigned Cohorts
  - `GET /api/trainers/{trainerId}/cohorts/paged` - Get Filtered Paged Assigned Cohorts
- [6. Admin Operations](#6-admin-operations)
  - `GET /api/admin/dashboard` - Admin System Dashboard Counters
  - `GET /api/admin/cohorts` - View All Cohorts Across System
  - `GET /api/admin/cohorts/paged` - View All Cohorts Paged & Filtered
  - `GET /api/admin/cohorts/service-lines` - Get Distinct Service Lines
  - `GET /api/admin/trainers` - View All Trainers Across System
  - `GET /api/admin/trainers/paged` - View All Trainers Paged & Filtered
  - `POST /api/admin/trainers` - Register New Trainer
  - `PUT /api/admin/trainers/{trainerId}` - Update Trainer Profile
  - `PATCH` / `PUT /api/admin/trainers/{trainerId}/status` - Toggle Trainer Availability
  - `DELETE /api/admin/trainers/{trainerId}` - Delete Trainer Profile
  - `POST /api/admin/trainers/bulk-delete` - Batch Bulk Delete Trainers
  - `PUT /api/admin/cohorts/{cohortId}/trainer` - Admin Manual Trainer Reassignment
  - `GET /api/admin/cohorts/export` - Export Global Allocation Excel Report
- [7. Notifications & Mailbox](#7-notifications--mailbox)
  - `GET /api/notifications/{userId}` - Get All User Notifications
  - `GET /api/notifications/{userId}/paged` - Get Paged User Notifications
  - `GET /api/notifications/{userId}/unread-count` - Get Unread Count
  - `PUT /api/notifications/{userId}/read-all` - Mark All Notifications as Read
- [8. Actuator & Swagger Endpoints](#8-actuator--swagger-endpoints)

---

## 1. Authentication

### `POST /api/auth/login` (also `/auth/login`)
Authenticates a user by login ID (email or username) and password.

- **Access**: Public
- **Request Headers**: `Content-Type: application/json`

#### Request Body
| Field | Type | Required | Constraints | Description |
| :--- | :--- | :---: | :--- | :--- |
| `loginId` | `string` | **Yes** | `@NotBlank` | User's email or username (e.g., `coach01`, `trainer01@cognizant.com`) |
| `password` | `string` | **Yes** | `@NotBlank` | Plain-text password (matched via BCrypt or direct match) |

```json
{
  "loginId": "coach01",
  "password": "password123"
}
```

#### Response - 200 OK (Success)
```json
{
  "success": true,
  "message": "Login successful",
  "userId": 1,
  "loginId": "coach01@cognizant.com",
  "name": "Jane Coach",
  "role": "COACH",
  "coachId": 1,
  "trainerId": null
}
```

#### Response - 401 Unauthorized (Failure)
```json
{
  "success": false,
  "message": "Invalid login ID or password",
  "userId": null,
  "loginId": null,
  "name": null,
  "role": null,
  "coachId": null,
  "trainerId": null
}
```

---

## 2. Health & System Checks

### `GET /api/health` or `GET /api/health/live` (also `/health`, `/health/live`)
Liveness check returning instant process status without database query overhead.

- **Access**: Public

#### Response - 200 OK
```json
{
  "success": true,
  "message": "TrainMate backend process is alive",
  "data": {
    "status": "UP",
    "timestamp": 1774232600123,
    "uptimeMs": 45120,
    "version": "1.0.0"
  },
  "errors": []
}
```

---

### `GET /api/health/ready` (also `/health/ready`)
Readiness check validating live MySQL connectivity via HikariCP pool.

- **Access**: Public

#### Response - 200 OK (Database Connected)
```json
{
  "success": true,
  "message": "TrainMate backend and database are ready",
  "data": {
    "status": "UP",
    "timestamp": 1774232600123,
    "database": "UP"
  },
  "errors": []
}
```

#### Response - 503 Service Unavailable (Database Down)
```json
{
  "success": false,
  "message": "TrainMate backend is degraded (Database unreachable)",
  "data": {
    "timestamp": 1774232600123,
    "database": "DOWN",
    "error": "Communications link failure"
  },
  "errors": []
}
```

---

## 3. Coach Operations

### `GET /api/coach/{coachId}/dashboard` (also `/coach/{coachId}/dashboard`)
Retrieves aggregated statistical KPI counters for a specific coach.

- **Path Parameters**:
  - `coachId` (`Long`): The coach's User ID.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Dashboard data retrieved successfully",
  "data": {
    "totalCohorts": 15,
    "assigned": 12,
    "unassigned": 3,
    "upcoming": 5
  },
  "errors": []
}
```

---

### `GET /api/coach/{coachId}/cohorts` (also `/coach/{coachId}/cohorts`)
Retrieves all cohorts initiated by the coach ordered by creation date descending.

- **Path Parameters**:
  - `coachId` (`Long`): Coach User ID.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Cohorts retrieved successfully",
  "data": [
    {
      "id": 1,
      "cohortCode": "QEA26SD001",
      "serviceLine": "QEA",
      "stream": "Software Development",
      "requiredSkill": "Java, Spring Boot",
      "numberOfTrainees": 25,
      "startDate": "2026-09-01",
      "endDate": "2026-11-30",
      "vertical": "Healthcare",
      "location": "Chennai",
      "status": "ASSIGNED",
      "coachId": 1,
      "coachName": "Jane Coach",
      "coachEmployeeId": "EMP_C1",
      "assignedTrainerId": 2,
      "assignedTrainerName": "John Trainer",
      "assignedTrainerEmployeeId": "EMP_T2",
      "allocationScore": 95.0,
      "allocationType": "AUTOMATIC",
      "allocationDate": "2026-08-15T10:30:00",
      "scoreBreakdown": {
        "skillScore": 40.0,
        "availabilityScore": 20.0,
        "workloadScore": 15.0,
        "experienceScore": 10.0,
        "previousCohortsScore": 10.0,
        "totalScore": 95.0,
        "explanation": "Skill Match: 40.0/40 (2/2 matched), Availability: 20.0/20, Workload: 15.0/15 (0/5), Experience: 10.0/15, Previous Cohorts: 10.0/10 (3 completed). Total: 95.0/100"
      },
      "createdAt": "2026-08-15T10:30:00",
      "updatedAt": "2026-08-15T10:30:00"
    }
  ],
  "errors": []
}
```

---

### `GET /api/coach/{coachId}/cohorts/paged` (also `/coach/{coachId}/cohorts/paged`)
Retrieves server-side paged, sorted, and filtered cohorts created by this coach.

- **Path Parameters**:
  - `coachId` (`Long`): Coach User ID.
- **Query Parameters**:
  - `query` (`string`, optional): Case-insensitive search on `cohortCode`, `requiredSkill`, or `location`.
  - `status` (`CohortStatus`, optional): `PENDING`, `PROCESSING`, `ASSIGNED`, `UNASSIGNED`, `ACTIVE`, `COMPLETED`, `CANCELLED`.
  - `serviceLine` (`string`, optional): Filter by service line name.
  - `page` (`integer`, optional, default: `0`): Zero-based page index.
  - `size` (`integer`, optional, default: `15`): Items per page.
  - `sort` (`string`, optional, default: `createdDate,desc`): Property and sort direction.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Cohorts retrieved successfully",
  "data": {
    "content": [
      {
        "id": 1,
        "cohortCode": "QEA26SD001",
        "serviceLine": "QEA",
        "stream": "Software Development",
        "requiredSkill": "Java, Spring Boot",
        "numberOfTrainees": 25,
        "startDate": "2026-09-01",
        "endDate": "2026-11-30",
        "vertical": "Healthcare",
        "location": "Chennai",
        "status": "ASSIGNED",
        "coachId": 1,
        "coachName": "Jane Coach",
        "coachEmployeeId": "EMP_C1",
        "assignedTrainerId": 2,
        "assignedTrainerName": "John Trainer",
        "assignedTrainerEmployeeId": "EMP_T2",
        "allocationScore": 95.0,
        "allocationType": "AUTOMATIC",
        "allocationDate": "2026-08-15T10:30:00",
        "createdAt": "2026-08-15T10:30:00",
        "updatedAt": "2026-08-15T10:30:00"
      }
    ],
    "pageable": {
      "pageNumber": 0,
      "pageSize": 15,
      "sort": { "sorted": true, "unsorted": false, "empty": false }
    },
    "totalElements": 1,
    "totalPages": 1,
    "last": true,
    "first": true,
    "size": 15,
    "number": 0,
    "numberOfElements": 1,
    "empty": false
  },
  "errors": []
}
```

---

### `POST /api/coach/{coachId}/cohorts` (also `/coach/{coachId}/cohorts`)
Creates a single new cohort and triggers the automatic 100-point allocation engine.

- **Path Parameters**:
  - `coachId` (`Long`): The coach's User ID.
- **Request Headers**: `Content-Type: application/json`

#### Request Body (`CreateCohortRequest`)
| Field | Type | Required | Constraints | Description |
| :--- | :--- | :---: | :--- | :--- |
| `cohortCode` | `string` | **Yes** | `@NotBlank`, max 30 chars, UNIQUE | Unique identifier code for the cohort |
| `serviceLine` | `string` | No | max 100 chars (Default: `"QEA"`) | Service line organizational unit |
| `stream` | `string` | No | max 100 chars (Default: `"Software Development"`) | Technical stream or track |
| `requiredSkill` | `string` | **Yes** | `@NotBlank`, max 300 chars | Comma/slash-separated technical skills |
| `numberOfTrainees`| `integer` | **Yes** | `@NotNull`, min 1, max 500 | Trainee headcount |
| `startDate` | `LocalDate` | **Yes** | `@NotNull` (Format: `YYYY-MM-DD`) | Training commencement date |
| `endDate` | `LocalDate` | **Yes** | `@NotNull` (Format: `YYYY-MM-DD`, $\ge$ startDate) | Completion date |
| `vertical` | `string` | No | max 100 chars (Default: `"Healthcare"`) | Industry vertical (e.g. Banking, Retail) |
| `location` | `string` | No | max 100 chars (Default: `"Chennai"`) | Delivery location / campus |

```json
{
  "cohortCode": "QEA26SD015",
  "serviceLine": "QEA",
  "stream": "Software Development",
  "requiredSkill": "Java, Spring Boot, MySQL",
  "numberOfTrainees": 30,
  "startDate": "2026-10-01",
  "endDate": "2026-12-31",
  "vertical": "Banking",
  "location": "Chennai"
}
```

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Cohort created and trainer allocated successfully",
  "data": {
    "id": 15,
    "cohortCode": "QEA26SD015",
    "serviceLine": "QEA",
    "stream": "Software Development",
    "requiredSkill": "Java, Spring Boot, MySQL",
    "numberOfTrainees": 30,
    "startDate": "2026-10-01",
    "endDate": "2026-12-31",
    "vertical": "Banking",
    "location": "Chennai",
    "status": "ASSIGNED",
    "coachId": 1,
    "coachName": "Jane Coach",
    "coachEmployeeId": "EMP_C1",
    "assignedTrainerId": 3,
    "assignedTrainerName": "Alan Turing",
    "assignedTrainerEmployeeId": "EMP_T3",
    "allocationScore": 96.5,
    "allocationType": "AUTOMATIC",
    "allocationDate": "2026-11-22T07:45:00",
    "scoreBreakdown": {
      "skillScore": 40.0,
      "availabilityScore": 20.0,
      "workloadScore": 15.0,
      "experienceScore": 15.0,
      "previousCohortsScore": 6.5,
      "totalScore": 96.5,
      "explanation": "Skill Match: 40.0/40 (3/3 matched), Availability: 20.0/20, Workload: 15.0/15 (0/5), Experience: 15.0/15, Previous Cohorts: 6.5/10 (2 completed). Total: 96.5/100"
    },
    "createdAt": "2026-11-22T07:45:00",
    "updatedAt": "2026-11-22T07:45:00"
  },
  "errors": []
}
```

#### Response - 409 Conflict (Duplicate Cohort Code)
```json
{
  "success": false,
  "message": "Cohort code already exists: QEA26SD015",
  "data": null,
  "errors": ["Cohort code already exists: QEA26SD015"]
}
```

---

### `POST /api/coach/{coachId}/cohorts/upload` (also `/coach/{coachId}/cohorts/upload`)
Batch processes multiple cohorts from an uploaded Excel file (`.xlsx`), runs batch validation, creates cohort records, and executes FIFO batch allocation.

- **Path Parameters**:
  - `coachId` (`Long`): Coach User ID.
- **Request Headers**: `Content-Type: multipart/form-data`
- **Form Data**:
  - `file` (`MultipartFile`): `.xlsx` or `.xls` spreadsheet (max 10MB).
  - Expected Columns in Row 1: `Cohort Code`, `Service Line`, `Stream`, `Required Skill`, `Number of Trainees`, `Start Date`, `End Date`, `Vertical`, `Location`.

#### Response - 200 OK (`CohortUploadResponse`)
```json
{
  "success": true,
  "message": "File processed",
  "data": {
    "totalRows": 5,
    "successfulRows": 4,
    "failedRows": 1,
    "errors": [
      {
        "row": 3,
        "message": "End Date cannot be before Start Date"
      }
    ],
    "allocatedCohorts": [
      {
        "id": 16,
        "cohortCode": "QEA26SD016",
        "serviceLine": "QEA",
        "stream": "Software Development",
        "requiredSkill": "Angular, TypeScript",
        "numberOfTrainees": 40,
        "startDate": "2026-10-01",
        "endDate": "2026-12-15",
        "vertical": "Insurance",
        "location": "Pune",
        "status": "ASSIGNED",
        "assignedTrainerId": 4,
        "assignedTrainerName": "Ada Lovelace",
        "allocationScore": 92.0
      }
    ]
  },
  "errors": []
}
```

---

## 4. Cohort Management

### `GET /api/cohorts/{cohortId}` (also `/cohorts/{cohortId}`)
Retrieves single cohort details including assigned trainer and explainable score breakdown.

- **Path Parameters**:
  - `cohortId` (`Long`): Primary key of the cohort.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Cohort retrieved successfully",
  "data": {
    "id": 1,
    "cohortCode": "QEA26SD001",
    "serviceLine": "QEA",
    "stream": "Software Development",
    "requiredSkill": "Java, Spring Boot",
    "numberOfTrainees": 25,
    "startDate": "2026-09-01",
    "endDate": "2026-11-30",
    "vertical": "Healthcare",
    "location": "Chennai",
    "status": "ASSIGNED",
    "coachId": 1,
    "coachName": "Jane Coach",
    "coachEmployeeId": "EMP_C1",
    "assignedTrainerId": 2,
    "assignedTrainerName": "John Trainer",
    "assignedTrainerEmployeeId": "EMP_T2",
    "allocationScore": 95.0,
    "allocationType": "AUTOMATIC",
    "allocationDate": "2026-08-15T10:30:00",
    "createdAt": "2026-08-15T10:30:00",
    "updatedAt": "2026-08-15T10:30:00"
  },
  "errors": []
}
```

---

### `PUT /api/cohorts/{cohortId}` (also `/cohorts/{cohortId}`)
Updates cohort parameters. If skills or dates are updated, the allocation engine re-evaluates the assigned trainer.

- **Path Parameters**:
  - `cohortId` (`Long`): Cohort ID.
- **Request Body**: `CreateCohortRequest` JSON.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Cohort updated successfully",
  "data": {
    "id": 1,
    "cohortCode": "QEA26SD001",
    "serviceLine": "QEA",
    "stream": "Software Development",
    "requiredSkill": "Java, Spring Boot, Microservices",
    "numberOfTrainees": 30,
    "startDate": "2026-09-01",
    "endDate": "2026-11-30",
    "vertical": "Healthcare",
    "location": "Chennai",
    "status": "ASSIGNED",
    "assignedTrainerId": 2,
    "assignedTrainerName": "John Trainer",
    "allocationScore": 94.0
  },
  "errors": []
}
```

---

### `PATCH /api/cohorts/{cohortId}/status` (also `/cohorts/{cohortId}/status`)
Updates cohort status lifecycle. Setting status to `CANCELLED` automatically frees the trainer's workload.

- **Path Parameters**:
  - `cohortId` (`Long`): Cohort ID.
- **Query Parameters**:
  - `status` (`string`, required): Status string (`PENDING`, `ASSIGNED`, `UNASSIGNED`, `ACTIVE`, `COMPLETED`, `CANCELLED`).

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Cohort status updated to COMPLETED",
  "data": {
    "id": 1,
    "cohortCode": "QEA26SD001",
    "status": "COMPLETED"
  },
  "errors": []
}
```

---

### `POST /api/cohorts/{cohortId}/reallocate` (also `/cohorts/{cohortId}/reallocate`)
One-click re-run of the 100-point allocation engine. Releases current trainer capacity and selects the best matching candidate.

- **Path Parameters**:
  - `cohortId` (`Long`): Cohort ID.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "100-point allocation engine re-evaluated successfully",
  "data": {
    "id": 1,
    "cohortCode": "QEA26SD001",
    "status": "ASSIGNED",
    "assignedTrainerId": 5,
    "assignedTrainerName": "Grace Hopper",
    "allocationScore": 98.0,
    "allocationType": "AUTOMATIC"
  },
  "errors": []
}
```

---

### `DELETE /api/cohorts/{cohortId}` (also `/cohorts/{cohortId}`)
Deletes a cohort, decrements assigned trainer workload, and purges linked notifications.

- **Path Parameters**:
  - `cohortId` (`Long`): Cohort ID.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Cohort deleted successfully and trainer workload released.",
  "data": null,
  "errors": []
}
```

---

### `POST /api/cohorts/bulk-delete` (also `/cohorts/bulk-delete`)
High-performance batch deletion of multiple cohorts using aggregated set queries.

- **Request Headers**: `Content-Type: application/json`

#### Request Body (`BulkDeleteRequest`)
| Field | Type | Required | Constraints | Description |
| :--- | :--- | :---: | :--- | :--- |
| `ids` | `List<Long>` | **Yes** | `@NotEmpty`, max 100 items | Array of Cohort IDs to delete |

```json
{
  "ids": [10, 11, 12]
}
```

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Successfully deleted 3 cohort(s).",
  "data": 3,
  "errors": []
}
```

---

### `GET /api/cohorts/sample-template` (also `/cohorts/sample-template`)
Generates and downloads an Excel template (`.xlsx`) pre-populated with headers and sample records.

- **Response Headers**:
  - `Content-Type`: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  - `Content-Disposition`: `attachment; filename=cohort_template.xlsx`
- **Response Body**: Binary `.xlsx` file stream.

---

## 5. Trainer Operations

### `GET /api/trainers/{trainerId}/dashboard` (also `/trainers/{trainerId}/dashboard`)
Retrieves dashboard KPI counters for the logged-in trainer.

- **Path Parameters**:
  - `trainerId` (`Long`): The Trainer primary key ID.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Trainer dashboard retrieved successfully",
  "data": {
    "active": 2,
    "upcoming": 1,
    "completed": 6,
    "unread": 3
  },
  "errors": []
}
```

---

### `GET /api/trainers/{trainerId}/cohorts` (also `/trainers/{trainerId}/cohorts`)
Retrieves all cohorts assigned to this trainer ordered chronologically by `startDate` ascending.

- **Path Parameters**:
  - `trainerId` (`Long`): Trainer ID.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Assigned cohorts retrieved successfully",
  "data": [
    {
      "id": 1,
      "cohortCode": "QEA26SD001",
      "serviceLine": "QEA",
      "stream": "Software Development",
      "requiredSkill": "Java, Spring Boot",
      "numberOfTrainees": 25,
      "startDate": "2026-09-01",
      "endDate": "2026-11-30",
      "vertical": "Healthcare",
      "location": "Chennai",
      "status": "ASSIGNED",
      "coachName": "Jane Coach",
      "assignedTrainerId": 2,
      "assignedTrainerName": "John Trainer",
      "allocationScore": 95.0
    }
  ],
  "errors": []
}
```

---

### `GET /api/trainers/{trainerId}/cohorts/paged` (also `/trainers/{trainerId}/cohorts/paged`)
Retrieves server-side paged and filtered cohorts assigned to this trainer.

- **Path Parameters**:
  - `trainerId` (`Long`): Trainer ID.
- **Query Parameters**:
  - `query` (`string`, optional): Search in `cohortCode`, `requiredSkill`, or `location`.
  - `status` (`CohortStatus`, optional): Filter by status (`ACTIVE`, `ASSIGNED`, `COMPLETED`, etc.).
  - `page` (`integer`, optional, default: `0`): Page index.
  - `size` (`integer`, optional, default: `15`): Items per page.
  - `sort` (`string`, optional, default: `startDate,asc`): Sort parameter.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Assigned cohorts retrieved successfully",
  "data": {
    "content": [ ...CohortResponse... ],
    "totalElements": 3,
    "totalPages": 1,
    "size": 15,
    "number": 0,
    "empty": false
  },
  "errors": []
}
```

---

## 6. Admin Operations

### `GET /api/admin/dashboard` (also `/admin/dashboard`)
Retrieves high-level platform statistics for administrator visibility.

- **Access**: Administrator (`Role.ADMIN`)

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Admin dashboard retrieved successfully",
  "data": {
    "totalCohorts": 48,
    "assignedCohorts": 42,
    "unassignedCohorts": 4,
    "pendingCohorts": 2,
    "activeCohorts": 18,
    "completedCohorts": 24,
    "totalTrainers": 16,
    "availableTrainers": 12,
    "unavailableTrainers": 4
  },
  "errors": []
}
```

---

### `GET /api/admin/cohorts` (also `/admin/cohorts`)
Retrieves all cohorts across the entire system.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "All cohorts retrieved successfully",
  "data": [ ...CohortResponse[]... ],
  "errors": []
}
```

---

### `GET /api/admin/cohorts/paged` (also `/admin/cohorts/paged`)
Server-side paginated, searchable, and filterable view of all cohorts.

- **Query Parameters**:
  - `query` (`string`, optional): Search in cohort code, required skill, or location.
  - `status` (`CohortStatus`, optional): Status filter (`PENDING`, `ASSIGNED`, `UNASSIGNED`, `ACTIVE`, `COMPLETED`, `CANCELLED`).
  - `serviceLine` (`string`, optional): Filter by service line.
  - `page` (`integer`, optional, default: `0`).
  - `size` (`integer`, optional, default: `20`).
  - `sort` (`string`, optional, default: `createdDate,desc`).

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Cohorts retrieved successfully",
  "data": {
    "content": [ ...CohortResponse... ],
    "totalElements": 48,
    "totalPages": 3,
    "size": 20,
    "number": 0
  },
  "errors": []
}
```

---

### `GET /api/admin/cohorts/service-lines` (also `/admin/cohorts/service-lines`)
Fetches all distinct service lines configured across all cohorts.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Service lines retrieved successfully",
  "data": [
    "Digital Engineering",
    "Enterprise Application Services",
    "QEA"
  ],
  "errors": []
}
```

---

### `GET /api/admin/trainers` (also `/admin/trainers`)
Retrieves all trainers in the system with calculated workload ratios and statuses.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "All trainers retrieved successfully",
  "data": [
    {
      "id": 1,
      "userId": 2,
      "name": "John Doe",
      "email": "trainer01@cognizant.com",
      "employeeId": "EMP_T1",
      "serviceLine": "QEA",
      "vertical": "Banking",
      "experienceYears": 6,
      "availableFrom": "2026-08-01",
      "availableTill": "2027-08-01",
      "currentWorkload": 2,
      "maximumWorkload": 5,
      "workloadRatio": "2/5",
      "previouslyHandledCohorts": 4,
      "status": "AVAILABLE",
      "skills": ["Java", "Spring Boot", "MySQL"]
    }
  ],
  "errors": []
}
```

---

### `GET /api/admin/trainers/paged` (also `/admin/trainers/paged`)
Server-side paginated list of trainers with search functionality.

- **Query Parameters**:
  - `search` (`string`, optional): Search in trainer name, email, or skills.
  - `page` (`integer`, optional, default: `0`).
  - `size` (`integer`, optional, default: `20`).
  - `sort` (`string`, optional, default: `id,asc`).

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Trainers retrieved successfully",
  "data": {
    "content": [ ...TrainerResponse... ],
    "totalElements": 16,
    "totalPages": 1,
    "size": 20,
    "number": 0
  },
  "errors": []
}
```

---

### `POST /api/admin/trainers` (also `/admin/trainers`)
Registers a new trainer, creates their user login (`Role.TRAINER`, default password `trainer123`), and links the trainer record.

- **Request Headers**: `Content-Type: application/json`

#### Request Body (`CreateTrainerRequest`)
| Field | Type | Required | Constraints | Description |
| :--- | :--- | :---: | :--- | :--- |
| `name` | `string` | **Yes** | `@NotBlank`, max 100 chars | Full name of trainer |
| `email` | `string` | **Yes** | `@NotBlank`, `@Email`, max 150 chars | Unique login email |
| `skillSet` | `string` | **Yes** | `@NotBlank`, max 500 chars | Comma-separated list of technical skills |
| `experienceYears`| `Double` | **Yes** | `@NotNull`, $\ge 0$, max 50 | Total years of professional experience |
| `availableFrom` | `LocalDate` | **Yes** | `@NotNull` (Format: `YYYY-MM-DD`) | Available start date |
| `availableTill` | `LocalDate` | **Yes** | `@NotNull` (Format: `YYYY-MM-DD`) | Available end date |
| `maxWorkload` | `Integer` | No | `@NotNull`, min 1, max 20 (Default: `5`)| Maximum concurrent cohort capacity |

```json
{
  "name": "Sarah Connor",
  "email": "sarah.connor@cognizant.com",
  "skillSet": "Java, Spring Boot, AWS, Docker",
  "experienceYears": 7.5,
  "availableFrom": "2026-09-01",
  "availableTill": "2027-08-31",
  "maxWorkload": 5
}
```

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Trainer created successfully",
  "data": {
    "id": 10,
    "userId": 18,
    "name": "Sarah Connor",
    "email": "sarah.connor@cognizant.com",
    "employeeId": "EMP_T10",
    "experienceYears": 7,
    "availableFrom": "2026-09-01",
    "availableTill": "2027-08-31",
    "currentWorkload": 0,
    "maximumWorkload": 5,
    "workloadRatio": "0/5",
    "previouslyHandledCohorts": 0,
    "status": "AVAILABLE",
    "skills": ["Java", "Spring Boot", "AWS", "Docker"]
  },
  "errors": []
}
```

---

### `PUT /api/admin/trainers/{trainerId}` (also `/admin/trainers/{trainerId}`)
Updates a trainer's profile, skill set, and workload limits.

- **Path Parameters**:
  - `trainerId` (`Long`): Trainer primary key.
- **Request Body**: `CreateTrainerRequest` JSON.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Trainer updated successfully",
  "data": { ...TrainerResponse... },
  "errors": []
}
```

---

### `PATCH` / `PUT /api/admin/trainers/{trainerId}/status` (also `/admin/trainers/{trainerId}/status`)
Toggles trainer availability status (`AVAILABLE` vs `UNAVAILABLE`).

- **Path Parameters**:
  - `trainerId` (`Long`): Trainer ID.
- **Query Parameters**:
  - `available` (`boolean`, required): `true` to set available for 1 year, `false` to set `availableTill` to yesterday.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Trainer availability updated",
  "data": {
    "id": 1,
    "status": "UNAVAILABLE"
  },
  "errors": []
}
```

---

### `DELETE /api/admin/trainers/{trainerId}` (also `/admin/trainers/{trainerId}`)
Deletes a trainer, automatically unassigns their cohorts (resets status to `UNASSIGNED`), purges notifications, and deletes the linked user account.

- **Path Parameters**:
  - `trainerId` (`Long`): Trainer ID.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Trainer deleted successfully and unassigned from cohorts",
  "data": null,
  "errors": []
}
```

---

### `POST /api/admin/trainers/bulk-delete` (also `/admin/trainers/bulk-delete`)
Batch deletion of multiple trainers in an atomic set query.

- **Request Headers**: `Content-Type: application/json`

#### Request Body (`BulkDeleteRequest`)
```json
{
  "ids": [5, 6, 7]
}
```

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Successfully deleted 3 trainer(s).",
  "data": 3,
  "errors": []
}
```

---

### `PUT /api/admin/cohorts/{cohortId}/trainer` (also `/admin/cohorts/{cohortId}/trainer`)
Admin manual trainer override/reassignment. Validates candidate eligibility, decrements previous trainer workload, increments new trainer workload, and dispatches email notifications to all parties.

- **Path Parameters**:
  - `cohortId` (`Long`): Target Cohort ID.
- **Query Parameters**:
  - `adminUserId` (`Long`, optional): Administrator User ID executing the override.
- **Request Headers**: `Content-Type: application/json`

#### Request Body (`TrainerOverrideRequest`)
| Field | Type | Required | Constraints | Description |
| :--- | :--- | :---: | :--- | :--- |
| `trainerId` | `Long` | **Yes** | `@NotNull` | Target Trainer ID |
| `reason` | `string` | No | max 500 chars | Justification for administrative override |

```json
{
  "trainerId": 4,
  "reason": "Specialized domain expertise in Healthcare HL7 compliance required"
}
```

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Trainer reassigned successfully",
  "data": {
    "id": 1,
    "cohortCode": "QEA26SD001",
    "status": "ASSIGNED",
    "assignedTrainerId": 4,
    "assignedTrainerName": "Ada Lovelace",
    "allocationScore": 92.0,
    "allocationType": "MANUAL_OVERRIDE",
    "allocationDate": "2026-11-22T07:50:00"
  },
  "errors": []
}
```

#### Response - 400 Bad Request (Trainer Ineligible)
```json
{
  "success": false,
  "message": "Trainer not eligible: Trainer has reached maximum workload (5/5)",
  "data": null,
  "errors": ["Trainer not eligible: Trainer has reached maximum workload (5/5)"]
}
```

---

### `GET /api/admin/cohorts/export` (also `/admin/cohorts/export`)
Generates and downloads a complete Excel report of all cohorts and their trainer allocations.

- **Response Headers**:
  - `Content-Type`: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  - `Content-Disposition`: `attachment; filename="cohort_allocations.xlsx"`
- **Response Body**: Binary `.xlsx` workbook.

---

## 7. Notifications & Mailbox

### `GET /api/notifications/{userId}` (also `/notifications/{userId}`)
Retrieves all notifications for a specific user ordered by creation date descending.

- **Path Parameters**:
  - `userId` (`Long`): Target User ID.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Notifications retrieved successfully",
  "data": [
    {
      "id": 101,
      "receiverUserId": 2,
      "receiverRole": "TRAINER",
      "title": "COHORT_ASSIGNMENT",
      "message": "You have been assigned to lead cohort QEA26SD001 (Java, Spring Boot).",
      "isRead": false,
      "createdAt": "2026-08-15T10:30:00"
    },
    {
      "id": 102,
      "receiverUserId": 2,
      "receiverRole": "TRAINER",
      "title": "TRAINER_REPLACED",
      "message": "You have been unassigned from cohort QEA26SD002.",
      "isRead": true,
      "createdAt": "2026-08-14T09:15:00"
    }
  ],
  "errors": []
}
```

---

### `GET /api/notifications/{userId}/paged` (also `/notifications/{userId}/paged`)
Retrieves paged notifications for a user.

- **Path Parameters**:
  - `userId` (`Long`): Target User ID.
- **Query Parameters**:
  - `page` (`integer`, optional, default: `0`).
  - `size` (`integer`, optional, default: `20`).
  - `sort` (`string`, optional, default: `createdDate,desc`).

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Notifications retrieved successfully",
  "data": {
    "content": [ ...NotificationResponse... ],
    "totalElements": 15,
    "totalPages": 1,
    "size": 20,
    "number": 0
  },
  "errors": []
}
```

---

### `GET /api/notifications/{userId}/unread-count` (also `/notifications/{userId}/unread-count`)
Returns the number of unread notifications for navbar badges.

- **Path Parameters**:
  - `userId` (`Long`): User ID.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "Unread count retrieved",
  "data": 4,
  "errors": []
}
```

---

### `PUT /api/notifications/{userId}/read-all` (also `/notifications/{userId}/read-all`)
Marks all unread notifications as read for the user in a single update query.

- **Path Parameters**:
  - `userId` (`Long`): User ID.

#### Response - 200 OK
```json
{
  "success": true,
  "message": "4 notifications marked as read",
  "data": 4,
  "errors": []
}
```

---

## 8. Actuator & Swagger Endpoints

### Spring Boot Actuator
- `GET /actuator` - Actuator endpoints catalog
- `GET /actuator/health` - Health status indicator (liveness and readiness)
- `GET /actuator/info` - Application release and Git metadata
- `GET /actuator/metrics` - JVM runtime metrics, memory, and HTTP response percentiles

### OpenAPI 3.0 & Swagger UI
- `GET /v3/api-docs` - Raw OpenAPI 3.0 JSON specification
- `GET /swagger-ui/index.html` (or `/swagger-ui.html`) - Interactive browser-based API testing portal

---

## 9. Quick Reference Table

| Method | Endpoint | Description | Role / Access |
| :--- | :--- | :--- | :--- |
| **POST** | `/api/auth/login` | Authenticate user & receive role details | Public |
| **GET** | `/api/health` or `/live` | Ultra-fast process liveness probe | Public |
| **GET** | `/api/health/ready` | MySQL database connection readiness probe | Public |
| **GET** | `/api/coach/{coachId}/dashboard` | Coach KPI dashboard statistics | Coach |
| **GET** | `/api/coach/{coachId}/cohorts` | List all cohorts for coach | Coach |
| **GET** | `/api/coach/{coachId}/cohorts/paged` | Search/filter paged cohorts for coach | Coach |
| **POST** | `/api/coach/{coachId}/cohorts` | Create cohort & run auto-allocation engine | Coach |
| **POST** | `/api/coach/{coachId}/cohorts/upload` | Upload `.xlsx` file for batch cohort creation | Coach |
| **GET** | `/api/cohorts/{cohortId}` | Retrieve cohort details & score breakdown | Any |
| **PUT** | `/api/cohorts/{cohortId}` | Update cohort details (triggers re-allocation) | Coach / Admin |
| **PATCH** | `/api/cohorts/{cohortId}/status` | Update cohort lifecycle status | Coach / Admin |
| **POST** | `/api/cohorts/{cohortId}/reallocate` | 1-Click trigger allocation re-run | Coach / Admin |
| **DELETE** | `/api/cohorts/{cohortId}` | Delete cohort & release trainer workload | Coach / Admin |
| **POST** | `/api/cohorts/bulk-delete` | Batch bulk delete cohorts | Coach / Admin |
| **GET** | `/api/cohorts/sample-template` | Download `.xlsx` cohort sample template | Coach / Admin |
| **GET** | `/api/trainers/{trainerId}/dashboard` | Trainer KPI dashboard statistics | Trainer |
| **GET** | `/api/trainers/{trainerId}/cohorts` | List all assigned cohorts for trainer | Trainer |
| **GET** | `/api/trainers/{trainerId}/cohorts/paged` | Search/filter paged assigned cohorts | Trainer |
| **GET** | `/api/admin/dashboard` | Global platform dashboard statistics | Admin |
| **GET** | `/api/admin/cohorts` | List all cohorts across system | Admin |
| **GET** | `/api/admin/cohorts/paged` | Search/filter all cohorts with pagination | Admin |
| **GET** | `/api/admin/cohorts/service-lines`| List distinct service lines | Admin |
| **GET** | `/api/admin/trainers` | List all trainers across system | Admin |
| **GET** | `/api/admin/trainers/paged` | Search/filter all trainers with pagination | Admin |
| **POST** | `/api/admin/trainers` | Register new trainer | Admin |
| **PUT** | `/api/admin/trainers/{trainerId}` | Update trainer profile & max workload | Admin |
| **PATCH** | `/api/admin/trainers/{trainerId}/status`| Toggle trainer availability status | Admin |
| **DELETE** | `/api/admin/trainers/{trainerId}` | Delete trainer & unassign active cohorts | Admin |
| **POST** | `/api/admin/trainers/bulk-delete` | Batch bulk delete trainers | Admin |
| **PUT** | `/api/admin/cohorts/{cohortId}/trainer`| Manual admin trainer reassignment override | Admin |
| **GET** | `/api/admin/cohorts/export` | Download global Excel allocation report | Admin |
| **GET** | `/api/notifications/{userId}` | List all notifications for a user | Any User |
| **GET** | `/api/notifications/{userId}/paged` | List paged notifications for a user | Any User |
| **GET** | `/api/notifications/{userId}/unread-count`| Get unread notifications count | Any User |
| **PUT** | `/api/notifications/{userId}/read-all`| Mark all notifications as read | Any User |
