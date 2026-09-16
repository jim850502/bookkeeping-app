# 運轉手帳本 5.0.2 相容層

此檔記錄由 5.0.2 Android 客戶端可驗證到的資料型別/欄位，供 bookkeeping-app 匯入器維護。

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
- `record_type`
- `record_id`
- `revision`
- `sequence`
- `deleted`
- `record_json`

## Income fields observed
- `fareAmount`
- `originalFare`
- `platformFeeAmount`
- `platformType`
- `customPlatformId`
- `dateTime`

## Expense fields observed
- `expense`
- `customCategoryId`
- `customCategoryName`
- `dateTime`

## Time-clock fields observed
- `clockInTime`
- `clockOutTime`
- `clockInMileageKm`
- `clockOutMileageKm`

## Sync protocol strings observed
- `v2/sync/pull`
- `v2/sync/push`
- `v2/sync/snapshot`
- `mutationId`
- `baseRevision`

`mutationId` is validated by the client as lowercase UUID v4. `baseRevision` is validated as a non-negative safe integer. For safety, bookkeeping-app currently treats this integration as import/read-only and does not push mutations into 運轉手帳本.

## Backup container strings observed
- `TAXIII-BACKUP`
- `plaintextSha256`
- gzip-related codec strings

The web importer intentionally does not attempt to modify the vendor cloud or bypass its authentication/App Check. It accepts user-provided/exported JSON/snapshot data and merges it locally.