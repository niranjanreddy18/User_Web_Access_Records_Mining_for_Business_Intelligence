# End-to-End Application Testing Report
**Project:** User Web Access Records Mining for Business Intelligence  
**Test Date:** 2026-11-13  
**Dataset Tested:** `website_monitoring_final_schema.csv` (980 records, 7 columns)  
**Verification Method:** Automated end-to-end integration execution, cross-verification via Pandas, and suite regression tests.

---

## 1. Test Summary

| Area | Result | Issues |
|------|--------|--------|
| CSV Upload | **PASS** | None. Headers detected, UUID job created, file validated. |
| Column Mapping | **PASS** | None. Exact 1:1 auto-mapping on all 7 columns. |
| Value Mapping | **PASS** | None. Standard aliases normalized; `video_play` and `wishlist` detected as unknown values. |
| Data Cleaning | **PASS** | None. All 980 valid rows retained, standardized schema verified. |
| Sessionization | **PASS** | None. 117 sessions across 40 users; 30-min boundary and idempotency verified. |
| Analytics | **PASS** | None. All metrics match raw CSV calculations (16:00 peak, 40 users, 661 page views). |
| Pattern Mining | **PASS** | None. 25 page patterns, 17 action patterns, 20 transitions, 20 common journeys mined. |
| BI Insights | **PASS** | None. 9 deterministic insights generated; no ungrounded claims. |
| Dashboard | **PASS** | None. Verified metrics feed Recharts KPI and chart components cleanly. |
| API Integration | **PASS** | None. CORS configured, status codes match specification, no file paths leaked. |
| Error Handling | **PASS** | None. Invalid stage ordering rejected (HTTP 400); unknown job rejected (HTTP 404). |
| Performance | **PASS** | None. 100,000 rows sessionized in 21.08s (within the 30-second PRD target). |

---

## 2. Detailed Verification

### 2.1 Upload & Column Mapping
- **Input:** `website_monitoring_final_schema.csv` (`user_id`, `timestamp`, `page_url`, `action`, `session_id`, `device`, `referrer`).
- **Result:** Uploaded successfully (HTTP 201), job ID created. Auto column mapping matched all 7 columns directly without requiring manual changes.

### 2.2 Value Mapping & Unknown Value Handling
- **Observed Actions:** `page_view`, `VIEW`, `checkout_completed`, `PURCHASE`, `view`, `search`, `SEARCH`, `cart_add`, `ADD_TO_CART`, `LOGIN`, `login`, `purchase`, `add_to_cart`, `video_play`, `wishlist`.
- **Normalization:**
  - `VIEW`, `view` $\to$ `page_view`
  - `checkout_completed`, `PURCHASE` $\to$ `purchase`
  - `SEARCH` $\to$ `search`
  - `cart_add`, `ADD_TO_CART` $\to$ `add_to_cart`
  - `LOGIN` $\to$ `login`
- **Unknown Actions:** `video_play` and `wishlist` were detected in `unknown_values` and mapped to `other`.

### 2.3 Data Cleaning & Quality Report
- Rows before: 980
- Rows after: 980 (0 removed, 0 duplicates, 0 invalid timestamps)
- Cleaned CSV written and saved.

### 2.4 Sessionization (30-minute Timeout)
- **Results:** 117 sessions generated across 40 users.
- **Idempotency:** Re-running `/api/sessionize` with `timeout_minutes=30` produced identical session counts (117) with no duplicate records.

### 2.5 Analytics & Metric Accuracy
- **Total Users:** 40 (matches Pandas unique count)
- **Total Sessions:** 117
- **Total Events:** 980
- **Peak Traffic Hour:** 16:00 (matches Pandas raw frequency count: 95 events at hour 16)
- **Action Counts:** `page_view`: 661, `add_to_cart`: 113, `purchase`: 81, `search`: 59, `login`: 58, `other`: 8
- **Primary Device:** Mobile (54.0%, 529 events; desktop: 388, tablet: 63)

### 2.6 Sequential Pattern Mining
- Mined 25 page patterns, 17 action patterns, 20 transitions, 20 common journeys.
- Top Journey: `/home` $\to$ `/products` (session count: 57, support: 48.7%).
- Top Transition: `/home` $\to$ `/products` (unique sessions: 57, transition count: 57).

### 2.7 BI Insights
Generated 9 data-backed insights:
1. `[INFO]` (navigation) **Common User Journey**: `/home → /products` occurred in 48.7% of sessions (57 sessions).
2. `[INFO]` (traffic) **Peak Traffic Period**: Most user activity occurred around 16:00.
3. `[INFO]` (content) **Most Visited Page**: `/home` was the most visited page with 137 page views.
4. `[INFO]` (content) **Least Visited Page**: Among recorded page views, `/` had the fewest visits (41).
5. `[INFO]` (engagement) **Average Session Engagement**: Users viewed an average of 5.65 pages per session with an average session duration of 2859.49 seconds.
6. `[INFO]` (device) **Primary Device**: mobile accounted for 54% of recorded activity.
7. `[INFO]` (exit) **Common Entry Page**: `/home` was the most common session entry page (99 sessions).
8. `[INFO]` (exit) **Common Exit Page**: `/checkout` was the most common session exit page (18 sessions).
9. `[POSITIVE]` (conversion) **Purchase Activity**: 81 purchase events were recorded.

---

## 3. Bugs Discovered & Fixes Applied

- **Bug 1: Page Refresh State Loss in Browser**
  - **File:** `frontend/src/hooks/useJob.jsx`
  - **Root Cause:** Job state was held purely in React in-memory state. Reloading on `/dashboard`, `/patterns`, or `/insights` reset the in-memory state, causing `ProtectedRoute` to redirect to `/upload`.
  - **Fix:** Added `sessionStorage` backing to `JobProvider` (`wam_active_job_state`) so active datasets persist through browser refreshes within the tab session.

---

## 4. Test Suite & Build Verification

- **Backend System Check:** `python manage.py check` $\to$ 0 issues.
- **Backend Test Suite:** `python manage.py test -v 2` $\to$ **156/156 passed** (100%).
- **Frontend Production Build:** `npm run build` $\to$ **0 errors** (built in 4.31s).
- **Performance:** 100,000 rows sessionized in 21.08 seconds (target: $\le$ 30 seconds).
