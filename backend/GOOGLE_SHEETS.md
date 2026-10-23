# Google Sheets visit source

The backend reads the retail_data worksheet from:
https://docs.google.com/spreadsheets/d/1wM7DTHizhg_A3h0qV3EhX4os4hk46uolW-ESQSJkgZs/edit?gid=1298094173

Google Sheets is the source of truth for visits. SQLite remains a local query cache for
the existing admin and sales API. Telegram polling is disabled in this mode. Nothing
is written back to Google Sheets.

## Run locally

From the backend directory:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python run.py --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ when frontend/dist has already been built.
For frontend development, run npm.cmd install and npm.cmd run dev in frontend.
The wildcard bind address 0.0.0.0 is not a browser URL; use 127.0.0.1 locally.
The existing admin dashboard refreshes its API data every 15 seconds.

Relevant configuration:

```ini
VISIT_DATA_SOURCE=google_sheets
GOOGLE_SHEETS_ID=1wM7DTHizhg_A3h0qV3EhX4os4hk46uolW-ESQSJkgZs
GOOGLE_SHEETS_TAB=retail_data
GOOGLE_SHEETS_GID=1298094173
GOOGLE_SHEETS_REFRESH_SECONDS=15
GOOGLE_SHEETS_CREDENTIALS_FILE=
```

The public CSV reader selects the worksheet by GOOGLE_SHEETS_GID. If the tab is
renamed or replaced, update both TAB and GID. The authenticated API reader selects
the worksheet by GOOGLE_SHEETS_TAB.

The default cache is backend/data/market_reports_sheets_test.db in test mode and
backend/data/market_reports_sheets.db in production. DATABASE_PATH overrides this.
Use a new database path: the sync refuses to overwrite an existing non-sheet visit
database or a cache belonging to another sheet. Transaction snapshots and upload
logs within the cache survive visit refreshes.

Set VISIT_DATA_SOURCE=telegram to use the original Telegram poller and database defaults.

## Refresh behavior

A background task starts fetching immediately after startup and checks again 15
seconds after each refresh completes. Change GOOGLE_SHEETS_REFRESH_SECONDS to tune
the interval (minimum 15 seconds). API requests never call Google Sheets directly.

Unchanged content skips rebuilding. Changed content is parsed and consolidated in
a separate in-memory database, then published in one SQLite transaction. Readers
see a complete snapshot. Edited and deleted rows are reflected in the next snapshot.

When Google is unavailable, the schema changes unexpectedly, or no valid report submissions
remain, the previous cache is retained. An intentionally emptied sheet is also
rejected to prevent accidentally wiping the dashboard.

GET /api/source/status (admin authentication required) reports the refresh state,
last attempt, last successful cache update, import counts, and any error.
GET /api/health reports the active visit data source.

## Column mapping and validation

Required headers are Sender_ID, Sender_Name, Name, Message_Date, Latitude, Longitude.
Other supported columns match the current retail_data export: Source_Channel,
Tel, Business, Purpose, Bank, Amount, Interest, Loan_Type, Tenure, Maturity,
Status, Potential_Level, Potential_Product, Remark, Raw_Text, Has_Image.
Estimated_USD and Has_Location are not part of the existing dashboard visit schema;
coordinates themselves determine GPS validity.

Naive timestamps are interpreted in Cambodia time (UTC+7) and stored as UTC.
ISO timestamps with offsets are supported. Single-digit hours are supported.
Rows without a merchant name, valid sender ID, valid date, or finite GPS coordinates
are retained in the dead-letter review queue and excluded from verified visit KPIs.
Missing merchant names may be recovered from Raw_Text. Blank rows are ignored.

Exact duplicate rows are removed. Record_ID or Message_ID can provide a stable
identity if added. Without either, identity is derived from Source_Channel,
Sender_ID, Message_Date, and Name. For repeated identities with corrected fields,
the later row in sheet order wins. IDs remain stable across unchanged refreshes,
row reordering, and edits to non-identity fields. Changing identity fields creates
a new visit identity. Merchant IDs derive from the earliest matching visit and may
change if that visit is removed or its identity changes.

Merchant matching uses phone/name compatibility and nearby GPS candidates, retaining
separate businesses at the same location. Visits rebuild merchant and RM aggregates.
The sheet contains a much larger history than the original dashboard sample data;
existing paginated API limits remain in place. Stats cover the entire valid cache.

## Private sheet access

Public read access currently works for this sheet. If it becomes private:

1. Enable the Google Sheets API in a Google Cloud project.
2. Create a service account and obtain its JSON credentials securely.
3. Share this spreadsheet with its client_email as Viewer.
4. Set GOOGLE_SHEETS_CREDENTIALS_FILE to the JSON file's absolute path.

Only the spreadsheets.readonly scope is requested. Never commit credentials.
For Docker, one option is backend/data/service_account_google.json (ignored by Git)
with GOOGLE_SHEETS_CREDENTIALS_FILE=/app/data/service_account_google.json; the existing
data volume makes that path available. Prefer a read-only secret mount in deployment.

Reference: https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get

## Tests

```powershell
python -B -m unittest tests.test_parser tests.test_tma tests.test_google_sheets tests.test_activity tests.test_daily_pulse tests.test_movement tests.test_sheets_api -v
```

Google Sheets tests use synthetic rows and temporary databases; no test modifies
the real spreadsheet. Live read-only import validation can use an isolated
temporary cache.

## Sales activity watcher

The default admin screen is Sales Activity. It observes reporting behavior using
sales_submissions, independent of the verified merchant visit tables.

A drop is a named merchant report with a valid Sender_ID and Message_Date. It counts
even if GPS or a photo is missing. Blank messages and rows without usable timestamps
do not create a timed drop. Duplicate message identities count once.

The watcher shows:
- Report drops per salesperson and date.
- First and last drop times in Cambodia time.
- Actual elapsed seconds between consecutive drops from the same Sender_ID.
- Average, median, and longest same-day gaps.
- An hourly submission chart and 14-day history per sender.
- A paginated drop timeline with GPS/photo completeness.
- Optional flags for gaps over 15, 30, 60, or 90 minutes.

There is no assumed SLA: the default is Show gaps only. Overnight gaps remain
visible in the timeline and are excluded from same-day averages and optional flags.
First-ever drops have no preceding gap. The first drop of a selected date retains
its actual predecessor from the preceding date. Page boundaries never reset gaps.

The initial date is the latest report date available in the cache. The screen
explicitly labels historical dates and offers View today. A date without submissions
shows zero drops; observed senders can still be listed using Include no-drop senders.
Submission gaps describe reporting cadence and do not establish working time.

The Target Acquisition screen and old conversion leaderboard/profile components
have been removed from the watcher frontend. Territory Coverage and the admin
Store Map are also removed. The watcher movement map and audit tools remain
available. Legacy transaction APIs remain available separately.

Admin API:
- GET /api/activity?date=YYYY-MM-DD&threshold_minutes=60
- GET /api/activity/{sender_id}/drops?date=YYYY-MM-DD&limit=100&offset=0

Omit threshold_minutes to return gaps without flags. Both endpoints require admin
authentication. The activity API reads the full local cache rather than the capped
merchant/report lists used by legacy screens.


## Movement by salesperson

Sales Activity includes a map with a stable color per Sender_ID, matching the
salesperson list and legend. All salespeople can be viewed together, or a selected
person can be shown alone. Numbered stops and direction arrows show chronological
GPS drops; the square stop marks the latest GPS report. Locate in the drop timeline
centers the corresponding point.

Lines join consecutive GPS reports for the same sender on the selected Cambodia
date. They never connect different people or different days. Reports without GPS
still count and keep their drop numbers; a dashed segment indicates intervening
reports without a location. Repeated coordinates stay at their reported position.
Connections and straight-line distances do not represent a recorded road route.
Segment tooltips show elapsed time between the two GPS reports, which may span
intervening drops without GPS.

GET /api/activity/routes?date=YYYY-MM-DD optionally accepts sender_id and requires
the same admin authentication as other activity endpoints. It reads all drops on
that date, independently of timeline pagination, and refreshes in the UI every 15 seconds.


## Daily activity workspace

Sales Activity is the first admin navigation item. Its daily summary shows GPS
completeness and same-day submission gaps. The team cadence chart uses every
sender's full ordered drop_times from the activity overview, including reports
without GPS and without the timeline pagination limit. Hourly bars compare all
reports with the selected salesperson. Filters find missing GPS or optionally
flagged gaps; the sender list can sort by drops, longest gaps, latest drop, or name.

Replay drops animates the selected sender's GPS stops in order, one stop per step.
Pause, the position slider, and Show full route allow exploration. Replay time
shows the actual report timestamp, not elapsed real-time travel. Switching sender
or date resets playback. Replay operates on cached local data and never writes to
Google Sheets.


## Daily RM pulse and first-drop recognition

Sales Activity uses a Live Pulse style layout: Daily RM Performance cards and a
latest-first notification feed sit beside the movement map. Selecting an RM
updates the map, hourly comparison, and full drop timeline. The feed can display
all RMs or the selected RM.

First submissions are evaluated per Sender_ID and Cambodia calendar date:
- Early Bird: the earliest first report at or before 09:30:00; exact timestamp ties share recognition.
- Late Start: each RM whose first report is strictly after 09:30:00, shown with a contrasting blue badge and banner.
- An RM with no report is unclassified, not automatically a late starter.
- Reports without GPS remain eligible. Later submissions never change that RM's first-drop classification.

The labels describe report timing, not physical arrival or attendance. Historical
dates are labelled explicitly. If all first reports are after the cutoff, there
is no Early Bird.

GET /api/activity/feed?date=YYYY-MM-DD supports sender_id, threshold_minutes,
limit (1-200, default 50), and offset. It requires admin authentication. Entries
include per-RM daily drop numbers, previous-drop gaps, and first-drop recognition.
The feed refreshes every 15 seconds. Initial loads and date/RM scope changes
establish a baseline; subsequently unseen report IDs show a NEW card and a
ten-second in-app notification. Repeated refreshes do not re-notify for those IDs.
These are local dashboard notifications; no external messages are sent.


## Compact Sales Activity notifications

Sales Activity now matches the Live Pulse arrangement on desktop: independently
scrolling RM performance and notification panels stay visible on the left, while
compact daily totals and a full-height movement map occupy the right. Daily rhythm
and the selected RM's full timeline are available as tabs, without pushing the
notification feed below the screen.

Each notification and new-report popup includes the RM, merchant, visit number
within that Cambodia date, total reported visits for that RM on the date, and the
gap since the preceding report from that same RM. A report without GPS is still a
reported visit. First-ever reports say No earlier drop. Previous-date gaps are
shown explicitly as across dates.

The feed's Late Drops tab lists first reports strictly after 09:30, using the
existing per-RM Late Start rule. GET /api/activity/feed accepts late_only=true;
filtering and pagination preserve full-day visit totals and visit sequence numbers.
Watching Late Drops continues polling all drops for new-report notifications.
The optional gap threshold flags long intervals separately from late first drops.
RM cards show the latest observed interval instead of the daily median.


## Movement map presentation

The summary card row and separate historical notice were removed to enlarge the
map. The selected date and a compact Historical badge remain in the heading.
Sales movement opens on the selected RM; All salespeople shows the complete team.

Routes use pale dashed lines, direction arrows, and dark GPS points. Explicit
Leaflet panes put every point above every route line, even where trails cross.
Selected stops have numbered markers with start/latest labels, a subtle latest
stop pulse, and animated dashes. Dotted connectors indicate intervening reports
without GPS. Reduced-motion preferences disable these animations. Actual GPS
coordinates and chronological connections are preserved.

Replay controls float within the map. Expand map opens a larger view; Collapse map
or Escape returns to the dashboard. Resizing reframes the visible GPS trail so
its reported stops remain within the map; background polling leaves the view alone.


## Combined RM Activity panel

Daily RM Performance and Daily Drop Notifications are combined into one RM Activity
panel. Each RM appears once, with their daily visit total, first-drop recognition,
latest merchant/report time, and interval since their previous drop. Latest activity
is the default sort. All RMs, Recent drops, and Late Start filters share the same
cards; advanced filters retain search, sort, missing-GPS and optional gap flags.

Selecting a card focuses its RM on the movement map and expands up to five latest
reports with visit sequence numbers, full-day totals, GPS completeness and gaps.
The full timeline remains available from each expanded card. Only the expanded
RM's report list is fetched; summary cards use the overview's latest merchant
fields without a request per RM.

Global new-report detection remains independent of the expanded card and filters.
Initial/date loads establish a baseline; unseen report IDs highlight their RM card
and show an in-app notification. Opening a card does not create notifications.
The map, replay, dark GPS points and light dashed trails remain available.

## Monitor review tools

The Quick review box is removed to give the RM list more space. Missing GPS,
no-drop and long-pause filters remain under Filters & first-drop highlights.
The reporting pause window is configured there; it is separate from the optional
threshold between completed drops. Elapsed-report indicators remain on RM cards.

The map scope toggle uses a colored sliding highlight: teal for All salespeople
and indigo/violet for Selected only. Reduced-motion preferences disable sliding.

For today's date the reference clock advances every 15 seconds. Historical dates
freeze the reference at the last team report on that date and display that time.
Historical dates without reports have no elapsed-time reference.

The movement map keeps the route unobstructed, with RM details in the left
Activity panel and on clicked report markers. The mobile map retains extra height
for easier route review and replay. Existing new-report popups and 15-second
refresh remain active.

## Channel and sender filters

RM Activity's Channel dropdown uses trimmed Source_Channel values from reports on
the selected Cambodia date, with distinct RM counts per channel. Blank values
appear as Unspecified channel. An RM can belong to multiple channels on a date;
channels from other dates do not count as membership on the selected date.

Channel selection and sender-name/ID search combine with the existing filters.
Search is case-insensitive, handles Unicode, and supports multiple name words in
either order. Both the RM list and movement map show matching people. An empty
match clears the selected RM and leaves the map empty. Clearing the search or
selecting All channels restores the matching people.

Channels filter people, not individual drops. Each matching RM's card, timeline,
recognition, visit numbering and route retain their full-day activity and actual
gaps. Expanded reports label their source channel. New-drop detection remains
global; opening an out-of-scope notification clears channel/name filters so the
reported person's activity is visible.

## Users-sheet login and access levels

The local dashboard now uses the Users worksheet in the same workbook. Required
columns are username, password, allowed_sources, role and is_active. Tele_ID and
branch are optional. Sign in using only the password column, exactly as stored;
no username or Telegram ID is entered. Passwords preserve spaces, case and Unicode.
Only active TRUE/1/yes rows with role admin, sro or rm can sign in. The matching
row supplies the account name, role and allowed_sources. Each password must be
unique across all nonempty Users rows, including inactive rows. Shared passwords
are rejected rather than selecting an account or combining permissions. Duplicate
account identities are also rejected. Changing a password to a shared value
invalidates existing sessions after the next Users refresh.

allowed_sources accepts comma, semicolon, pipe or newline-separated source names,
or a JSON array of names. All or * explicitly grants all sources. A blank or
malformed value grants none. Matching ignores outer spaces and case, but does
not guess misspelled channel names or grant implicit access based on role/branch.

Permissions apply server-side to activity, dates, feed, routes, timelines,
merchants, RMs, reports, stats, DLQ and the Field Sales Portal. Restricted
statistics and merchant/RM dimensions are rebuilt from permitted records in a
request-local in-memory snapshot, so a shared merchant cannot expose a later
report from another source. Gaps and first-drop recognition use permitted records.
Unscoped Excel/transaction endpoints require All-source access; transaction
uploads additionally require role admin. Both portals require Users login.

Users permissions refresh on requests at most every USERS_REFRESH_SECONDS
(default 60 seconds). Password, source, role, branch or active-status changes
invalidate existing sessions after refresh. Users-sheet failures deny new data
access; there is no automatic environment-admin fallback or localhost bypass.
Sessions default to eight hours and logout revokes the bearer session in this
local server process. A generated random AUTH_SECRET_KEY is saved in the ignored
local .env. Existing old admin tokens must sign in again with Users credentials.
AUTH_SOURCE=env is an explicit compatibility mode for non-sheet installations
and isolated legacy tests; it is not used by the configured local dashboard.

Passwords and verifier tags never enter API responses, application logs or the
SQLite cache. The Users sheet currently allows public-link reads. Restrict the
workbook sharing and configure GOOGLE_SHEETS_CREDENTIALS_FILE for read-only
service-account access to keep the credential sheet private. Changing sharing
without configuring that access will make sheet-backed sign-in unavailable.

## Automatic dashboard refresh

The backend checks Google Sheets every 15 seconds after the previous check finishes;
a changed workbook must finish rebuilding its cache before new drops become visible.
The dashboard polls every 15 seconds after the preceding request finishes, without
overlapping calls to the same view. Returning to the tab or reconnecting triggers
a check immediately. The footer distinguishes dashboard checks from successful
Google Sheets checks; an unchanged sheet still advances the sheet-check timestamp.
A failed request and a failed sheet sync have separate saved-data messages.
An explicitly selected historical date remains selected during refresh.
Channel restrictions are enforced with bound SQL source names after normalizing
distinct channel names, avoiding Python callbacks for every report during polling.

## Map drop details

Click any GPS stop to open its visit card: Name, Tel, Business, Bank, Amount,
Interest, Loan type, Maturity and Status, plus the salesperson, drop time and channel.
The card uses that submission's visit record, never the merchant's latest aggregated
record. Original amount, interest and maturity text is preserved without guessing
currency, units or dates. Empty and N/A fields display "Not reported"; zero values
are retained. A single usable phone number supports a tap-to-call link.

Details are loaded through the authenticated /api/activity/drops/{drop_id} endpoint
only while a popup is open, and refresh automatically. It applies the same
allowed_sources permissions; denied or unknown drop IDs return 404. Routine map
and notification polling remains lightweight.
