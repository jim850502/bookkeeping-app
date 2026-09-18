# Taxiii Android companion → localhost bridge contract

This document defines the remaining handoff without bypassing Firebase Auth or Firebase App Check.

## Goal

The companion must use a **legitimate signed-in session owned by the user**. It must not forge App Check, extract or persist refresh tokens, defeat TLS/security controls, or access another account.

The browser never receives Firebase credentials.

Flow:

1. Taxiii/authorized Android-side component obtains a fresh Firebase ID token and Firebase App Check token through the normal Firebase SDK flow.
2. The Android-side component sends both over loopback/ADB-local transport to the bridge `POST /session`.
3. The bridge stores them in RAM only for at most 45 minutes.
4. GitHub Pages calls bridge `/pull` or `/snapshot` with `deviceId`/cursor data only.
5. Bridge adds the two short-lived headers and calls the verified read-only Taxiii endpoints.
6. On HTTP 401/403 the bridge erases the session immediately.

## Bridge request

`POST http://127.0.0.1:8765/session`

```json
{
  "idToken": "<fresh Firebase ID token>",
  "appCheck": "<fresh Firebase App Check token>"
}
```

These values are intentionally not accepted as URL parameters and must never be logged.

Success:

```json
{
  "ok": true,
  "stored": "memory-only",
  "expiresInSeconds": 2700
}
```

## Health check

`GET http://127.0.0.1:8765/health`

Returns only metadata such as `sessionReady` and `sessionAgeSeconds`; it never returns either credential.

## Session clearing

`POST http://127.0.0.1:8765/session/clear`

Erases both values from RAM.

## Read-only invariant

The bridge contains no route for:

- `/v2/sync/push`
- `/v1/sync/ack`
- `/v1/sync/devices/register`
- device revoke/delete
- backup upload/restore

Only `/v2/sync/pull` and `/v2/sync/snapshot` are proxied upstream.

## Android implementation boundary

A standalone third-party APK cannot legitimately call `FirebaseAuth.getInstance()` for another app and inherit that app's authenticated Firebase user/App Check identity. Therefore the companion cannot simply be built as an unrelated APK and magically read Taxiii's session.

Acceptable implementations require one of these user-controlled/authorized integration points:

- an official/exported integration supplied by Taxiii;
- code running in an app build/account context where Firebase legitimately issues the credentials to that code;
- an explicit user-driven export from Taxiii that the bookkeeping app imports.

Until one of those integration points exists, `/session` is a transport contract, not a claim that credentials can be obtained from the stock APK automatically.

## deviceId

The verified Taxiii installation identifier is a lowercase UUID v4 and is used as the sync `deviceId`. The bookkeeping UI may remember `deviceId`; this is not an authentication credential.

## Stock APK 5.0.2 integration check

Static inspection of the user's supplied production APK confirms Firebase Auth and Firebase App Check are bundled, including Play Integrity token handling. No verified exported integration was found that would let an unrelated companion app inherit the stock app's authenticated Firebase/App Check identity.

Therefore the production-safe implementation must not attempt to impersonate the stock APK, forge App Check, read another app's private storage, or defeat Android app isolation. The direct-cloud button remains gated on a legitimate session handoff. Until such a handoff exists, the supported usable path is explicit Taxiii backup/export import; the bridge stays read-only and ready for an authorized handoff if Taxiii exposes one later.
