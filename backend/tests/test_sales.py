import unittest
from fastapi.testclient import TestClient
from src.market_bot.app import app

class TestSalesRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_sales_profile_fallback_and_specific(self):
        # 1. Fallback query (no telegram_id)
        res = self.client.get("/api/sales/profile")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("current_rm", data)
        self.assertIn("available_rms", data)
        self.assertGreater(len(data["available_rms"]), 0)

        # 2. Specific active RM
        rm_tg_id = data["available_rms"][0]["telegram_user_id"]
        res_specific = self.client.get(f"/api/sales/profile?telegram_id={rm_tg_id}")
        self.assertEqual(res_specific.status_code, 200)
        self.assertEqual(res_specific.json()["current_rm"]["telegram_user_id"], rm_tg_id)

    def test_sales_today_dashboard(self):
        res = self.client.get("/api/sales/today?ref_date=2026-10-05")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("kpis", data)
        self.assertIn("territory", data)
        self.assertIn("followups_to_prioritize", data)
        self.assertIn("visits_today", data)
        self.assertIn("team_activity", data)
        self.assertGreaterEqual(data["kpis"]["visits_today"], 0)

    def test_sales_store_map(self):
        res = self.client.get("/api/sales/store-map?limit=20")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("stores", data)
        self.assertIn("total_stores_in_view", data)
        self.assertIn("team_today_summary", data)

    def test_sales_customers_list(self):
        res = self.client.get("/api/sales/customers")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("summary", data)
        self.assertIn("all_customers", data)
        self.assertIn("overdue", data)

    def test_sales_visits_feed(self):
        res = self.client.get("/api/sales/visits?time_range=all")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_visits", data)
        self.assertIn("grouped_sections", data)
        self.assertIn("insight_banner", data)

    def test_sales_merchant_detail(self):
        # Grab a store id from store map
        map_res = self.client.get("/api/sales/store-map?limit=1")
        self.assertEqual(map_res.status_code, 200)
        stores = map_res.json()["stores"]
        if stores:
            m_id = stores[0]["id"]
            res = self.client.get(f"/api/sales/merchants/{m_id}")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["id"], m_id)
            self.assertIn("onboarding", data)
            self.assertIn("timeline", data)
            self.assertIn("contact", data)

class TestSalesPagination(unittest.TestCase):
    """Keyset pagination invariants for the infinite-scroll lists.

    These guard the failure modes that are invisible until a user scrolls:
    duplicated or skipped rows between pages, and search silently only
    covering the rows already paged into the client.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        prof = cls.client.get("/api/sales/profile").json()
        cls.tg = prof["current_rm"]["telegram_user_id"]

    def _walk(self, url, key_path, **params):
        """Page through an endpoint until has_more is false; return all ids."""
        ids, cursor, pages = [], None, 0
        while True:
            q = dict(params, cursor=cursor)
            q = {k: v for k, v in q.items() if v is not None}
            res = self.client.get(url, params=q)
            self.assertEqual(res.status_code, 200)
            data = res.json()

            if key_path == "customers":
                page_ids = [x["id"] for x in data["all_customers"]]
            else:
                page_ids = [v["id"] for g in data["grouped_sections"] for v in g["visits"]]

            ids.extend(page_ids)
            pages += 1
            cursor = data["next_cursor"]
            if not data["has_more"]:
                break
            self.assertIsNotNone(cursor, "has_more=true must supply a cursor")
            self.assertLess(pages, 200, "pagination did not terminate")

        return ids, pages, data

    def test_customer_pages_have_no_duplicates_and_cover_the_total(self):
        ids, pages, last = self._walk("/api/sales/customers", "customers", limit=30)
        self.assertGreater(pages, 1, "expected the default customer set to span multiple pages")
        self.assertEqual(len(ids), len(set(ids)), "duplicate customer rows across pages")
        self.assertEqual(len(ids), last["total"], "paged rows did not cover the reported total")

    def test_visit_pages_have_no_duplicates_and_cover_the_total(self):
        ids, pages, last = self._walk(
            "/api/sales/visits", "visits", time_range="all", limit=40
        )
        self.assertGreater(pages, 1, "expected the full visit history to span multiple pages")
        self.assertEqual(len(ids), len(set(ids)), "duplicate visit rows across pages")
        self.assertEqual(len(ids), last["total_visits"], "paged rows did not cover the reported total")

    def test_paged_traversal_matches_single_query_order(self):
        """Walking pages must yield exactly the same rows in the same order
        as asking for everything at once — this catches any keyset predicate
        that skips, repeats or reorders rows at a page boundary."""
        paged_ids, cursor, pages = [], None, 0
        while True:
            params = {"telegram_id": self.tg, "time_range": "all", "limit": 40}
            if cursor:
                params["cursor"] = cursor
            data = self.client.get("/api/sales/visits", params=params).json()

            paged_ids.extend(v["id"] for g in data["grouped_sections"] for v in g["visits"])
            pages += 1
            cursor = data["next_cursor"]
            if not data["has_more"]:
                break
            self.assertLess(pages, 200)

        # limit=200 exceeds this RM's full history, so this is the whole set in one shot
        full = self.client.get(
            "/api/sales/visits",
            params={"telegram_id": self.tg, "time_range": "all", "limit": 200},
        ).json()
        full_ids = [v["id"] for g in full["grouped_sections"] for v in g["visits"]]

        self.assertGreater(pages, 1, "expected this history to span multiple pages")
        self.assertEqual(
            paged_ids, full_ids,
            "paged traversal diverged from the single-query order",
        )

    def test_customer_name_sort_is_ascending_across_pages(self):
        rows, cursor, pages = [], None, 0
        while True:
            params = {"telegram_id": self.tg, "sort_by": "name", "limit": 25}
            if cursor:
                params["cursor"] = cursor
            res = self.client.get("/api/sales/customers", params=params)
            self.assertEqual(res.status_code, 200)
            data = res.json()

            rows.extend((c["name"], c["id"]) for c in data["all_customers"])
            pages += 1
            cursor = data["next_cursor"]
            if not data["has_more"]:
                break
            self.assertLess(pages, 200)

        ids = [i for _, i in rows]
        self.assertEqual(len(ids), len(set(ids)), "duplicate customer ids across pages")

        names = [n for n, _ in rows]
        # Names may legitimately repeat (two branches sharing a name), so compare
        # against the sorted copy of the same multiset rather than asserting uniqueness.
        self.assertEqual(names, sorted(names), "name sort is not ascending across page boundaries")

    def test_search_spans_whole_set_not_just_loaded_page(self):
        """A term matching rows outside page 1 must still be found.

        Regression guard: with client-side filtering this found nothing,
        because the matching rows had never been paged into the client.
        """
        first = self.client.get(
            "/api/sales/customers", params={"telegram_id": self.tg, "limit": 30}
        ).json()
        page_one_names = {c["name"] for c in first["all_customers"]}

        everything = self.client.get(
            "/api/sales/customers", params={"telegram_id": self.tg, "limit": 100}
        ).json()
        off_page = [
            c["name"] for c in everything["all_customers"] if c["name"] not in page_one_names
        ]
        if not off_page:
            self.skipTest("no merchant outside page 1 for this RM")

        target = off_page[0]
        found = self.client.get(
            "/api/sales/customers",
            params={"telegram_id": self.tg, "search": target, "limit": 30},
        ).json()
        self.assertIn(
            target,
            [c["name"] for c in found["all_customers"]],
            "search failed to reach a row beyond page 1",
        )

    def test_status_filter_is_applied_server_side(self):
        signed = self.client.get(
            "/api/sales/customers",
            params={"telegram_id": self.tg, "status": "SIGNED", "limit": 100},
        ).json()
        for c in signed["all_customers"]:
            self.assertTrue(
                c["is_onboarded"]
                or c["stage"] in ("CONVERTED", "EXISTING")
                or bool(c.get("has_cmcb")),
                f"{c['name']} is not signed but appeared under status=SIGNED",
            )

        unsigned = self.client.get(
            "/api/sales/customers",
            params={"telegram_id": self.tg, "status": "NOT_SIGNED", "limit": 100},
        ).json()
        for c in unsigned["all_customers"]:
            self.assertNotIn(
                c["stage"],
                ("CONVERTED", "EXISTING"),
                f"{c['name']} is signed but appeared under status=NOT_SIGNED",
            )

    def test_malformed_cursor_restarts_instead_of_erroring(self):
        res = self.client.get(
            "/api/sales/customers",
            params={"telegram_id": self.tg, "cursor": "!!!not-a-real-cursor!!!", "limit": 5},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["all_customers"]), 5)

    def test_sort_modes_are_stable_across_pages(self):
        for sort_by in ("recent", "longest_unvisited", "name"):
            ids, _, _ = self._walk(
                "/api/sales/customers", "customers", sort_by=sort_by, limit=25
            )
            self.assertEqual(len(ids), len(set(ids)), f"{sort_by} produced duplicates across pages")


    def test_visit_dates_endpoint_returns_unique_sorted_dates(self):
        res = self.client.get("/api/sales/visits/dates", params={"telegram_id": self.tg})
        self.assertEqual(res.status_code, 200)
        dates = res.json().get("dates", [])
        self.assertIsInstance(dates, list)
        self.assertGreater(len(dates), 0, "expected active visit dates for Liza Soy")
        # Must be unique
        self.assertEqual(len(dates), len(set(dates)), "duplicate dates in visit dates index")
        # Must be ordered descending
        self.assertEqual(dates, sorted(dates, reverse=True), "dates index must be ordered DESC")

    def test_jump_date_returns_records_on_or_before_requested_date(self):
        jump_date = "2026-09-17"
        res = self.client.get(
            "/api/sales/visits",
            params={"telegram_id": self.tg, "jump_date": jump_date, "time_range": "all"},
        )
        self.assertEqual(res.status_code, 200)
        sections = res.json().get("grouped_sections", [])
        self.assertGreater(len(sections), 0)
        first_section = sections[0]
        self.assertEqual(first_section["date_slug"], jump_date, "jump_date should start at requested date")
        for sec in sections:
            self.assertLessEqual(sec["date_slug"], jump_date)

if __name__ == "__main__":
    unittest.main()


