from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import ugettext as _

from itou.jobs.models import Appellation
from itou.www.siaes_views.forms import SiaeSearchForm
from itou.siaes.models import Siae
from itou.utils.pagination import pager
from itou.utils.urls import get_safe_url


def search(request, template_name="siaes/search_results.html"):

    form = SiaeSearchForm(data=request.GET)
    siaes_page = None

    if form.is_valid():

        city = form.cleaned_data["city"]
        distance_km = form.cleaned_data["distance"]
        kind = form.cleaned_data["kind"]

        siaes = Siae.active_objects.within(
            city.coords, distance_km
        ).prefetch_jobs_through(is_active=True)
        if kind:
            siaes = siaes.filter(kind=kind)
        siaes_page = pager(siaes, request.GET.get("page"), items_per_page=10)

    context = {"form": form, "siaes_page": siaes_page}
    return render(request, template_name, context)


def card(request, siret, template_name="siaes/card.html"):
    """
    SIAE's card (or "Fiche" in French).
    """
    queryset = Siae.active_objects.prefetch_jobs_through(is_active=True)
    siae = get_object_or_404(queryset, siret=siret)
    next_url = get_safe_url(request, "next")
    context = {"next": next_url, "siae": siae}
    return render(request, template_name, context)


@login_required
def configure_jobs(request, siret, template_name="siaes/configure_jobs.html"):
    """
    Configure an SIAE's jobs.
    """
    queryset = Siae.active_objects.prefetch_jobs_through().member_required(request.user)
    siae = get_object_or_404(queryset, siret=siret)

    if request.method == "POST":

        current_codes = set(
            siae.jobs_through.values_list("appellation__code", flat=True)
        )
        submitted_codes = set(request.POST.getlist("code"))

        codes_to_create = submitted_codes - current_codes
        # It is assumed that the codes to delete are not submitted (they must
        # be removed from the DOM via JavaScript). Instead, they are deducted.
        codes_to_delete = current_codes - submitted_codes
        codes_to_update = current_codes - codes_to_delete

        if codes_to_create or codes_to_delete or codes_to_update:

            # Create.
            for code in codes_to_create:
                appellation = Appellation.objects.get(code=code)
                through_defaults = {
                    "is_active": bool(request.POST.get(f"is_active-{code}"))
                }
                siae.jobs.add(appellation, through_defaults=through_defaults)

            # Delete.
            if codes_to_delete:
                appellations = Appellation.objects.filter(code__in=codes_to_delete)
                siae.jobs.remove(*appellations)

            # Update.
            for job_through in siae.jobs_through.filter(
                appellation__code__in=codes_to_update
            ):
                is_active = bool(
                    request.POST.get(f"is_active-{job_through.appellation.code}")
                )
                if job_through.is_active != is_active:
                    job_through.is_active = is_active
                    job_through.save()

            messages.success(request, _("Mise à jour effectuée !"))
            return HttpResponseRedirect(
                reverse("siaes_views:configure_jobs", kwargs={"siret": siae.siret})
            )

    context = {"siae": siae}
    return render(request, template_name, context)