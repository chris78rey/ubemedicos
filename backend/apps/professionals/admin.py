from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import (
    ProfessionalProfile,
    ProfessionalDocument,
    ProfessionalVerificationSubmission,
    ProfessionalVerificationEvent,
)
from .services import (
    submit_professional_for_verification,
    assign_verification_submission,
    start_verification_review,
    review_professional_document,
    request_submission_correction,
    approve_verification_submission,
    reject_verification_submission,
)


class ProfessionalDocumentInline(admin.TabularInline):
    model = ProfessionalDocument
    extra = 0
    fields = (
        "document_type",
        "original_name",
        "file_path",
        "review_status",
        "reviewer_notes",
        "uploaded_at",
        "reviewed_at",
    )
    readonly_fields = ("uploaded_at", "reviewed_at")


@admin.action(description="Enviar selección a validación")
def action_submit_for_verification(modeladmin, request, queryset):
    ok_count = 0

    for profile in queryset:
        try:
            submit_professional_for_verification(
                professional=profile, actor=request.user
            )
            ok_count += 1
        except ValidationError as exc:
            modeladmin.message_user(
                request,
                f"{profile.user.email}: {' | '.join(exc.messages)}",
                level=messages.ERROR,
            )

    if ok_count:
        modeladmin.message_user(
            request,
            f"Se enviaron {ok_count} perfiles a validación.",
            level=messages.SUCCESS,
        )


@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "specialty",
        "license_number",
        "verification_status",
        "public_profile_enabled",
        "city",
        "province",
        "created_at",
    )
    list_filter = ("verification_status", "public_profile_enabled", "province", "city")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "license_number",
    )
    inlines = [ProfessionalDocumentInline]
    actions = [action_submit_for_verification]


@admin.action(description="Aprobar documentos seleccionados")
def action_approve_documents(modeladmin, request, queryset):
    ok_count = 0

    for doc in queryset:
        submission = (
            ProfessionalVerificationSubmission.objects.filter(
                professional=doc.professional,
                status__in=[
                    ProfessionalVerificationSubmission.Status.SUBMITTED,
                    ProfessionalVerificationSubmission.Status.UNDER_REVIEW,
                ],
            )
            .order_by("-submitted_at")
            .first()
        )

        if not submission:
            modeladmin.message_user(
                request,
                f"Documento {doc.id}: no existe solicitud abierta para el profesional.",
                level=messages.ERROR,
            )
            continue

        try:
            review_professional_document(
                submission=submission,
                document=doc,
                actor=request.user,
                decision=ProfessionalDocument.ReviewStatus.APPROVED,
                notes=doc.reviewer_notes or "",
            )
            ok_count += 1
        except ValidationError as exc:
            modeladmin.message_user(
                request,
                f"Documento {doc.id}: {' | '.join(exc.messages)}",
                level=messages.ERROR,
            )

    if ok_count:
        modeladmin.message_user(
            request,
            f"Se aprobaron {ok_count} documentos.",
            level=messages.SUCCESS,
        )


@admin.action(description="Rechazar documentos seleccionados")
def action_reject_documents(modeladmin, request, queryset):
    ok_count = 0

    for doc in queryset:
        submission = (
            ProfessionalVerificationSubmission.objects.filter(
                professional=doc.professional,
                status__in=[
                    ProfessionalVerificationSubmission.Status.SUBMITTED,
                    ProfessionalVerificationSubmission.Status.UNDER_REVIEW,
                ],
            )
            .order_by("-submitted_at")
            .first()
        )

        if not submission:
            modeladmin.message_user(
                request,
                f"Documento {doc.id}: no existe solicitud abierta para el profesional.",
                level=messages.ERROR,
            )
            continue

        try:
            review_professional_document(
                submission=submission,
                document=doc,
                actor=request.user,
                decision=ProfessionalDocument.ReviewStatus.REJECTED,
                notes=doc.reviewer_notes
                or "Rechazado desde admin. Debe detallarse el motivo.",
            )
            ok_count += 1
        except ValidationError as exc:
            modeladmin.message_user(
                request,
                f"Documento {doc.id}: {' | '.join(exc.messages)}",
                level=messages.ERROR,
            )

    if ok_count:
        modeladmin.message_user(
            request,
            f"Se rechazaron {ok_count} documentos.",
            level=messages.SUCCESS,
        )


@admin.register(ProfessionalDocument)
class ProfessionalDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "professional",
        "document_type",
        "original_name",
        "review_status",
        "uploaded_at",
        "reviewed_at",
    )
    list_filter = ("document_type", "review_status")
    search_fields = ("professional__user__email", "original_name", "file_path")
    actions = [action_approve_documents, action_reject_documents]


@admin.action(description="Asignar a mi usuario")
def action_assign_to_me(modeladmin, request, queryset):
    ok_count = 0

    for submission in queryset:
        try:
            assign_verification_submission(
                submission=submission,
                actor=request.user,
                assignee=request.user,
            )
            ok_count += 1
        except ValidationError as exc:
            modeladmin.message_user(
                request,
                f"Solicitud {submission.id}: {' | '.join(exc.messages)}",
                level=messages.ERROR,
            )

    if ok_count:
        modeladmin.message_user(
            request,
            f"Se asignaron {ok_count} solicitudes.",
            level=messages.SUCCESS,
        )


@admin.action(description="Pasar a under_review")
def action_start_review(modeladmin, request, queryset):
    ok_count = 0

    for submission in queryset:
        try:
            start_verification_review(
                submission=submission,
                actor=request.user,
            )
            ok_count += 1
        except ValidationError as exc:
            modeladmin.message_user(
                request,
                f"Solicitud {submission.id}: {' | '.join(exc.messages)}",
                level=messages.ERROR,
            )

    if ok_count:
        modeladmin.message_user(
            request,
            f"Se movieron {ok_count} solicitudes a under_review.",
            level=messages.SUCCESS,
        )


@admin.action(description="Pedir corrección usando reviewer_notes")
def action_request_correction(modeladmin, request, queryset):
    ok_count = 0

    for submission in queryset:
        try:
            request_submission_correction(
                submission=submission,
                actor=request.user,
                notes=submission.reviewer_notes,
            )
            ok_count += 1
        except ValidationError as exc:
            modeladmin.message_user(
                request,
                f"Solicitud {submission.id}: {' | '.join(exc.messages)}",
                level=messages.ERROR,
            )

    if ok_count:
        modeladmin.message_user(
            request,
            f"Se marcaron {ok_count} solicitudes con needs_correction.",
            level=messages.SUCCESS,
        )


@admin.action(description="Aprobar solicitud")
def action_approve_submission(modeladmin, request, queryset):
    ok_count = 0

    for submission in queryset:
        try:
            approve_verification_submission(
                submission=submission,
                actor=request.user,
                notes=submission.reviewer_notes or "",
            )
            ok_count += 1
        except ValidationError as exc:
            modeladmin.message_user(
                request,
                f"Solicitud {submission.id}: {' | '.join(exc.messages)}",
                level=messages.ERROR,
            )

    if ok_count:
        modeladmin.message_user(
            request,
            f"Se aprobaron {ok_count} solicitudes.",
            level=messages.SUCCESS,
        )


@admin.action(description="Rechazar solicitud usando reviewer_notes")
def action_reject_submission(modeladmin, request, queryset):
    ok_count = 0

    for submission in queryset:
        try:
            reject_verification_submission(
                submission=submission,
                actor=request.user,
                notes=submission.reviewer_notes,
            )
            ok_count += 1
        except ValidationError as exc:
            modeladmin.message_user(
                request,
                f"Solicitud {submission.id}: {' | '.join(exc.messages)}",
                level=messages.ERROR,
            )

    if ok_count:
        modeladmin.message_user(
            request,
            f"Se rechazaron {ok_count} solicitudes.",
            level=messages.SUCCESS,
        )


@admin.register(ProfessionalVerificationSubmission)
class ProfessionalVerificationSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "professional",
        "status",
        "submitted_at",
        "assigned_admin",
        "reviewed_by",
        "reviewed_at",
    )
    list_filter = ("status",)
    search_fields = ("professional__user__email",)
    readonly_fields = ("submitted_at", "reviewed_at")
    actions = [
        action_assign_to_me,
        action_start_review,
        action_request_correction,
        action_approve_submission,
        action_reject_submission,
    ]


@admin.register(ProfessionalVerificationEvent)
class ProfessionalVerificationEventAdmin(admin.ModelAdmin):
    list_display = ("id", "submission", "event_type", "created_by", "created_at")
    list_filter = ("event_type",)
    search_fields = ("submission__professional__user__email",)
    readonly_fields = ("created_at",)
