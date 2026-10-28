"""Company knowledge source disclosure tests: project ACL is independent of team membership."""
import hashlib
import json
import unittest
from unittest.mock import patch
import test_platform_v4 as base

from teamspace.company_evidence import workspace_knowledge_graph
from teamspace.store import Problem, now


class CompanyEvidenceTests(unittest.TestCase):
    def setUp(self):
        base.PlatformTests.setUp(self)
        self.patch=patch("teamspace.company_evidence.store_for",lambda _:self.s)
        self.patch.start()
        self.private_task=self.s.create_task(self.p2,1,{"title":"PRIVATE_PRODUCT_RESEARCH_TASK"})["id"]
        # a is a member/owner of p2, but b is only a member of p1 within the same workspace.
        with self.s.connection(True) as c:
            self.doc=self.s.put_object(c,self.p2,"document","PRIVATE_SOURCE_FILE_TITLE",
                 "Secret confidential source facts",1,
                 data={"task_id":self.private_task,"adopted":True,"document_kind":"summary"},
                 status="ready")
        self.pub=self.s.publish_document(self.w,self.doc,1,1)["id"]
    def tearDown(self):
        self.patch.stop()
        base.PlatformTests.tearDown(self)
    def view(self,actor=None,workspace=None):
        return workspace_knowledge_graph(workspace or self.w,user=actor or self.a,server=object())
    @staticmethod
    def kinds(view,name):
        return [n for n in view["nodes"] if n["type"]==name]

    def test_workspace_member_sees_published_but_not_private_source(self):
        public=self.view(self.b)
        self.assertEqual(public["counts"]["published_total"],1)
        self.assertEqual(public["counts"]["restricted_source_count"],1)
        published=self.kinds(public,"published_knowledge")
        self.assertEqual(len(published),1)
        self.assertEqual(published[0]["source_visibility"],"restricted")
        self.assertEqual(self.kinds(public,"document"),[])
        self.assertEqual(self.kinds(public,"task"),[])
        encoded=json.dumps(public,ensure_ascii=False)
        # Title was intentionally copied into the published company snapshot.
        # Do not suppress authorized published content: hide *source* IDs and
        # private task/document fields when source-project permission is absent.
        self.assertIn("PRIVATE_SOURCE_FILE_TITLE",encoded)
        self.assertNotIn("PRIVATE_PRODUCT_RESEARCH_TASK",encoded)
        self.assertNotIn(self.doc,encoded)
        self.assertNotIn(self.private_task,encoded)
        self.assertNotIn(self.p2,encoded)

    def test_project_member_gets_provenance_and_snapshot_revision(self):
        view=self.view(self.a)
        self.assertEqual(view["counts"]["visible_source_count"],1)
        self.assertEqual(self.kinds(view,"published_knowledge")[0]["source_visibility"],"authorized")
        docs=self.kinds(view,"document")
        self.assertEqual(docs[0]["revision"],1)
        self.assertTrue(docs[0]["current_matches_published_revision"])
        self.assertEqual(len(self.kinds(view,"task")),1)
        self.assertTrue(any(e["relation"]=="document_explicitly_published_as_snapshot" for e in view["edges"]))
        self.assertFalse(view["sensitivity_classification_enabled"])

    def test_membership_grants_are_rechecked_each_request(self):
        first=self.view(self.b)
        self.assertEqual(first["counts"]["restricted_source_count"],1)
        self.s.set_member(self.p2,1,self.b,"member")
        second=self.view(self.b)
        self.assertEqual(second["counts"]["visible_source_count"],1)
        self.assertEqual(len(self.kinds(second,"document")),1)
        self.s.remove_member(self.p2,1,2)
        third=self.view(self.b)
        self.assertEqual(third["counts"]["restricted_source_count"],1)
        self.assertEqual(self.kinds(third,"document"),[])

    def test_outside_company_cannot_read_even_published_summary(self):
        with self.assertRaises(Problem):
            self.view(self.c)
        # c's own unrelated company shouldn't have our publications
        other=self.view(self.c,self.other)
        self.assertEqual(other["counts"]["published_total"],0)

    def test_publication_withdrawn_not_displayed_original_doc_preserved(self):
        before=self.view(self.a)
        self.assertEqual(before["counts"]["published_total"],1)
        self.s.withdraw_knowledge(self.w,self.pub,1)
        after=self.view(self.a)
        self.assertEqual(after["counts"]["published_total"],0)
        self.assertEqual(self.kinds(after,"published_knowledge"),[])
        self.assertTrue(self.s.object(self.doc,1,"document"))

    def test_public_snapshot_freezes_source_revision_and_detects_source_update(self):
        before=self.view(self.a)
        pubhash=self.kinds(before,"published_knowledge")[0]["body_sha256"]
        with self.s.connection(True) as c:
            c.execute("UPDATE team_objects SET revision=revision+1,body=? WHERE id=?",
                      ("New source content no longer equal to published frozen version",self.doc))
        after=self.view(self.a)
        self.assertEqual(self.kinds(after,"published_knowledge")[0]["body_sha256"],pubhash)
        self.assertFalse(self.kinds(after,"document")[0]["current_matches_published_revision"])

    def test_removed_project_never_leaks_title_through_company_graph(self):
        with self.s.connection(True) as c:
            c.execute("INSERT INTO team_admin_trash(target_id,workspace_id,project_id,kind,title,previous_json,deleted_at,deleted_by,batch_id) VALUES(?,?,?,?,?,?,?,?,?)",
                      (self.p2,self.w,self.p2,"project","Removed project","{}",now(),1,"retired"))
        view=self.view(self.a)
        # Company publication itself is still a frozen explicit snapshot until
        # its own status is withdrawn; archival hides the project original.
        self.assertEqual(self.kinds(view,"document"),[])
        self.assertEqual(self.kinds(view,"task"),[])
        self.assertEqual(self.kinds(view,"published_knowledge")[0]["source_visibility"],"restricted")


if __name__=="__main__":unittest.main()
