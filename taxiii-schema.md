# 運轉手帳本 5.0.2 相容層

此檔記錄由 5.0.2 Android 客戶端 AOT 可驗證到的資料型別、同步協定與驗證流程，供 bookkeeping-app 相容層維護。

## Ledger record types
- `ledger_income`
- `ledger_expense`
- `ledger_time_clock`
- `ledger_work_schedule`
- `ledger_setting`
- `ledger_income_target`
- `ledger_custom_platform`
- `ledger_custom_expense`

## Cloud record envelope
同步 API 使用 camelCase：`recordType`, `recordId`, `revision`, `sequence`, `deleted`, `payload`，另觀察到 `updatedAt`。本機 SQLite shadow 使用 snake_case：`record_type`, `record_id`, `record_json` 等。

## Verified read-only sync protocol
Base: `https://backup.23.95.165.241.sslip.io`

### Pull
`POST /v2/sync/pull`

Request:
```json
{"deviceId":"<uuid-v4>","cursor":0,"limit":100}
```

Response envelope:
```json
{"records":[],"nextCursor":0,"headSequence":0,"hasMore":false}
```

### Snapshot
`POST /v2/sync/snapshot`

Request:
```json
{"deviceId":"<uuid-v4>","snapshotSequence":1,"afterRecordType":null,"afterRecordId":null,"limit":100}
```

Response envelope:
```json
{"records":[],"snapshotSequence":1,"hasMore":false,"nextPage":null}
```

`nextPage`, when present, contains `recordType` and `recordId` and is fed into the next snapshot request as `afterRecordType` / `afterRecordId`.

## Device identity / registration
The installation ID is persisted by the Android client under SharedPreferences key `taxiii.cloud_sync.installation_id.v1`. It is a canonical lowercase UUID v4 and is used as the cloud sync `deviceId`.

`POST /v1/sync/devices/register`

Descriptor:
```json
{"deviceId":"<installation uuid-v4>","name":"<device name>","platform":"<platform>"}
```

Registration response wraps a `device` object and includes `activeDeviceCount` and `maxDevices`.

## Authentication flow verified from AOT
The request token provider performs the following flow:

1. Initialize Firebase and obtain the current Firebase Auth user.
2. Require an authenticated user and verified email.
3. Call `User.getIdToken()` with its default optional argument. In FlutterFire this is the non-forced-refresh path; the provider does not explicitly request a forced refresh at this call site.
4. Prefer `FirebaseAppCheck.getLimitedUseToken()` when the provider mode requests it; the alternate branch calls `FirebaseAppCheck.getToken()`.
5. Re-read the current Firebase user and verify the account has not changed while credentials were being issued.
6. Build request credentials from UID, Firebase ID token and App Check token.

Authenticated cloud requests include:
- `Authorization: Bearer <Firebase ID token>`
- `X-Firebase-AppCheck: <App Check token>`
- `Accept: application/json`
- `Content-Type: application/json`

The integration must use credentials obtained by the user's legitimate authenticated app/session. It must not forge or bypass Firebase Auth or App Check, and must not persist short-lived tokens in GitHub Pages/local source files.

## Income fields observed
- `fareAmount`
- `actualIncome`
- `originalFare`
- `platformFeeAmount`
- `platformFee`
- `platformType`
- `customPlatformId`
- `dateTime`
- `createdAt`
- `note`

## Expense fields observed
- `amount`
- `category`
- `customCategoryId`
- `customCategoryName`
- `customCategoryColorValue`
- `customCategoryIconCodePoint`
- `dateTime`
- `createdAt`
- `note`

## Time-clock fields observed
- `clockInTime`
- `clockOutTime`
- `mileage`

## Write-side strings observed but intentionally not implemented
- `v2/sync/push`
- `mutationId`
- `baseRevision`

`mutationId` is validated by the client as lowercase UUID v4. `baseRevision` is validated as a non-negative safe integer. bookkeeping-app keeps the vendor-cloud integration read-only until write semantics are independently verified.

## Backup container strings observed
- `TAXIII-BACKUP`
- `plaintextSha256`
- gzip-related codec strings

The web importer does not modify the vendor cloud or bypass its authentication/App Check. It accepts user-provided/exported data and the sync adapter is restricted to read-only pull/snapshot operations.
