import datetime

from django.test import TestCase
from django.urls import reverse

from itou.job_applications.models import JobApplication, JobApplicationWorkflow
from itou.users.factories import DEFAULT_PASSWORD
from itou.job_applications.factories import (
    JobApplicationSentByAuthorizedPrescriberOrganizationFactory,
    JobApplicationSentByJobSeekerFactory,
)


class ProcessViewsTest(TestCase):
    def test_details_for_siae(self):
        """Display the details of a job application."""

        job_application = JobApplicationSentByAuthorizedPrescriberOrganizationFactory()
        siae_user = job_application.to_siae.members.first()
        self.client.login(username=siae_user.email, password=DEFAULT_PASSWORD)

        url = reverse(
            "apply:details_for_siae", kwargs={"job_application_id": job_application.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_process(self):
        """Ensure that the `process` transition is triggered."""

        job_application = JobApplicationSentByAuthorizedPrescriberOrganizationFactory()
        siae_user = job_application.to_siae.members.first()
        self.client.login(username=siae_user.email, password=DEFAULT_PASSWORD)

        url = reverse(
            "apply:process", kwargs={"job_application_id": job_application.pk}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        next_url = reverse(
            "apply:details_for_siae", kwargs={"job_application_id": job_application.pk}
        )
        self.assertEqual(response.url, next_url)

        job_application = JobApplication.objects.get(pk=job_application.pk)
        self.assertTrue(job_application.state.is_processing)

    def test_refuse(self):
        """Ensure that the `refuse` transition is triggered."""

        job_application = JobApplicationSentByAuthorizedPrescriberOrganizationFactory(
            state=JobApplicationWorkflow.STATE_PROCESSING
        )
        self.assertTrue(job_application.state.is_processing)
        siae_user = job_application.to_siae.members.first()
        self.client.login(username=siae_user.email, password=DEFAULT_PASSWORD)

        url = reverse("apply:refuse", kwargs={"job_application_id": job_application.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        post_data = {
            "refusal_reason": job_application.REFUSAL_REASON_OTHER,
            "answer": "",
        }
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "answer",
            response.context["form"].errors,
            "Answer is mandatory with REFUSAL_REASON_OTHER.",
        )

        post_data = {
            "refusal_reason": job_application.REFUSAL_REASON_OTHER,
            "answer": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        }
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 302)

        next_url = reverse(
            "apply:details_for_siae", kwargs={"job_application_id": job_application.pk}
        )
        self.assertEqual(response.url, next_url)

        job_application = JobApplication.objects.get(pk=job_application.pk)
        self.assertTrue(job_application.state.is_refused)

    def test_postpone(self):
        """Ensure that the `postpone` transition is triggered."""

        job_application = JobApplicationSentByAuthorizedPrescriberOrganizationFactory(
            state=JobApplicationWorkflow.STATE_PROCESSING
        )
        self.assertTrue(job_application.state.is_processing)
        siae_user = job_application.to_siae.members.first()
        self.client.login(username=siae_user.email, password=DEFAULT_PASSWORD)

        url = reverse(
            "apply:postpone", kwargs={"job_application_id": job_application.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        post_data = {"answer": ""}
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 302)

        next_url = reverse(
            "apply:details_for_siae", kwargs={"job_application_id": job_application.pk}
        )
        self.assertEqual(response.url, next_url)

        job_application = JobApplication.objects.get(pk=job_application.pk)
        self.assertTrue(job_application.state.is_postponed)

    def test_accept(self):
        """Ensure that the `accept` transition is triggered."""

        job_application = JobApplicationSentByAuthorizedPrescriberOrganizationFactory(
            state=JobApplicationWorkflow.STATE_PROCESSING
        )
        self.assertTrue(job_application.state.is_processing)
        siae_user = job_application.to_siae.members.first()
        self.client.login(username=siae_user.email, password=DEFAULT_PASSWORD)

        url = reverse("apply:accept", kwargs={"job_application_id": job_application.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        today = datetime.date.today()
        post_data = {"date_of_hiring": today.strftime("%d/%m/%Y"), "answer": ""}
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 302)

        next_url = reverse(
            "apply:details_for_siae", kwargs={"job_application_id": job_application.pk}
        )
        self.assertEqual(response.url, next_url)

        job_application = JobApplication.objects.get(pk=job_application.pk)
        self.assertEqual(job_application.date_of_hiring, today)
        self.assertTrue(job_application.state.is_accepted)

    def test_eligibility(self):
        """Test eligibility."""

        job_application = JobApplicationSentByAuthorizedPrescriberOrganizationFactory(
            state=JobApplicationWorkflow.STATE_PROCESSING
        )
        self.assertTrue(job_application.state.is_processing)
        siae_user = job_application.to_siae.members.first()
        self.client.login(username=siae_user.email, password=DEFAULT_PASSWORD)

        self.assertFalse(job_application.job_seeker.has_eligibility_diagnosis)

        url = reverse(
            "apply:eligibility", kwargs={"job_application_id": job_application.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        post_data = {
            "faire_face_a_des_difficultes_administratives_ou_juridiques": [
                "prendre_en_compte_une_problematique_judiciaire"
            ],
            "criteres_administratifs_de_niveau_1": ["beneficiaire_du_rsa"],
        }
        response = self.client.post(url, data=post_data)
        self.assertEqual(response.status_code, 302)

        next_url = reverse(
            "apply:details_for_siae", kwargs={"job_application_id": job_application.pk}
        )
        self.assertEqual(response.url, next_url)

        self.assertTrue(job_application.job_seeker.has_eligibility_diagnosis)

    def test_eligibility_wrong_state_for_job_application(self):
        """The eligibility diagnosis page must only be accessible in `STATE_PROCESSING`."""
        for state in [
            JobApplicationWorkflow.STATE_POSTPONED,
            JobApplicationWorkflow.STATE_ACCEPTED,
            JobApplicationWorkflow.STATE_REFUSED,
            JobApplicationWorkflow.STATE_OBSOLETE,
        ]:
            job_application = JobApplicationSentByJobSeekerFactory(state=state)
            siae_user = job_application.to_siae.members.first()
            self.client.login(username=siae_user.email, password=DEFAULT_PASSWORD)
            url = reverse(
                "apply:eligibility", kwargs={"job_application_id": job_application.pk}
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)
            self.client.logout()


class ProcessTemplatesTest(TestCase):
    """
    Test actions available in the details template for the different.
    states of a job application.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up data for the whole TestCase."""
        cls.job_application = (
            JobApplicationSentByAuthorizedPrescriberOrganizationFactory()
        )
        cls.siae_user = cls.job_application.to_siae.members.first()

        kwargs = {"job_application_id": cls.job_application.pk}
        cls.url_details = reverse("apply:details_for_siae", kwargs=kwargs)
        cls.url_process = reverse("apply:process", kwargs=kwargs)
        cls.url_eligibility = reverse("apply:eligibility", kwargs=kwargs)
        cls.url_refuse = reverse("apply:refuse", kwargs=kwargs)
        cls.url_postpone = reverse("apply:postpone", kwargs=kwargs)
        cls.url_accept = reverse("apply:accept", kwargs=kwargs)

    def test_details_template_for_state_new(self):
        """Test actions available when the state is new."""
        self.client.login(username=self.siae_user.email, password=DEFAULT_PASSWORD)
        response = self.client.get(self.url_details)
        # Test template content.
        self.assertIn(self.url_process, str(response.content))
        self.assertNotIn(self.url_eligibility, str(response.content))
        self.assertNotIn(self.url_refuse, str(response.content))
        self.assertNotIn(self.url_postpone, str(response.content))
        self.assertNotIn(self.url_accept, str(response.content))

    def test_details_template_for_state_processing(self):
        """Test actions available when the state is processing."""
        self.client.login(username=self.siae_user.email, password=DEFAULT_PASSWORD)
        self.job_application.state = JobApplicationWorkflow.STATE_PROCESSING
        self.job_application.save()
        response = self.client.get(self.url_details)
        # Test template content.
        self.assertNotIn(self.url_process, str(response.content))
        self.assertIn(self.url_eligibility, str(response.content))
        self.assertNotIn(self.url_refuse, str(response.content))
        self.assertNotIn(self.url_postpone, str(response.content))
        self.assertNotIn(self.url_accept, str(response.content))

    def test_details_template_for_state_postponed(self):
        """Test actions available when the state is postponed."""
        self.client.login(username=self.siae_user.email, password=DEFAULT_PASSWORD)
        self.job_application.state = JobApplicationWorkflow.STATE_POSTPONED
        self.job_application.save()
        response = self.client.get(self.url_details)
        # Test template content.
        self.assertNotIn(self.url_process, str(response.content))
        self.assertNotIn(self.url_eligibility, str(response.content))
        self.assertIn(self.url_refuse, str(response.content))
        self.assertNotIn(self.url_postpone, str(response.content))
        self.assertIn(self.url_accept, str(response.content))

    def test_details_template_for_other_states(self):
        """Test actions available for other states."""
        self.client.login(username=self.siae_user.email, password=DEFAULT_PASSWORD)
        for state in [
            JobApplicationWorkflow.STATE_ACCEPTED,
            JobApplicationWorkflow.STATE_REFUSED,
            JobApplicationWorkflow.STATE_OBSOLETE,
        ]:
            self.job_application.state = state
            self.job_application.save()
            response = self.client.get(self.url_details)
            # Test template content.
            self.assertNotIn(self.url_process, str(response.content))
            self.assertNotIn(self.url_eligibility, str(response.content))
            self.assertNotIn(self.url_refuse, str(response.content))
            self.assertNotIn(self.url_postpone, str(response.content))
            self.assertNotIn(self.url_accept, str(response.content))