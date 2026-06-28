"""
Tenants - Forms.

Forms for public service request and admin management.
"""
from django import forms


class ServiceRequestForm(forms.Form):
    """Public service request form shown on /<company_code>/request/."""

    customer_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Full name", "class": "form-control"}),
    )
    customer_phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={"placeholder": "Phone number", "class": "form-control"}),
    )
    customer_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "Email (optional)", "class": "form-control"}),
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"placeholder": "Service address", "class": "form-control", "rows": 2}),
    )
    service_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"placeholder": "Describe your issue", "class": "form-control", "rows": 3}),
    )
    preferred_time = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Preferred time", "class": "form-control"}),
    )


class CompanyPageForm(forms.Form):
    """Admin form for editing company page settings."""

    title = forms.CharField(max_length=200, required=False)
    intro_text = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    contact_phone = forms.CharField(max_length=20, required=False)
    contact_email = forms.EmailField(required=False)
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    working_hours = forms.CharField(max_length=200, required=False)
    is_request_form_enabled = forms.BooleanField(required=False)
    is_published = forms.BooleanField(required=False)


class CompanyServiceForm(forms.Form):
    """Admin form for creating/editing company services."""

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "عنوان خدمات"}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "توضیحات"}),
    )
    base_price = forms.IntegerField(
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "قیمت پایه (تومان)"}),
    )
    is_active = forms.BooleanField(required=False, initial=True)


class TechnicianCreateForm(forms.Form):
    """Admin form for creating a technician."""

    username = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "مثلاً tech_ali", "style": "direction:ltr;"}),
    )
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "09121234567", "style": "direction:ltr;"}),
    )
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "نام"}),
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "نام خانوادگی"}),
    )
    is_available = forms.BooleanField(required=False, initial=True)
    skills = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "مهارت‌ها (با کاما جدا کنید)"}),
    )


class TechnicianEditForm(forms.Form):
    """Admin form for editing a technician."""

    username = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": "readonly", "style": "direction:ltr;background:#f1f5f9;"}),
    )
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "09121234567", "style": "direction:ltr;"}),
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "برای تغییر رمز پر کنید"}),
    )
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    is_available = forms.BooleanField(required=False)
    skills = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "مهارت‌ها (با کاما جدا کنید)"}),
    )


class TechnicianServiceRateForm(forms.Form):
    """One row in the technician service rate inline table."""

    item_definition = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="— انتخاب آیتم —",
        widget=forms.Select(attrs={"class": "form-control form-control-sm"}),
    )
    fixed_wage_rial = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "form-control form-control-sm", "placeholder": "مثلاً 4000000"}
        ),
    )
    is_active = forms.BooleanField(required=False)

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.orders.models import OrderItemDefinition

        if company is not None:
            self.fields["item_definition"].queryset = (
                OrderItemDefinition.objects.filter(
                    company=company,
                    kind=OrderItemDefinition.Kind.NUMBER,
                    is_active=True,
                )
                .select_related("category")
                .order_by("category__title", "title")
            )
        else:
            self.fields["item_definition"].queryset = OrderItemDefinition.objects.none()

    def clean(self):
        cleaned = super().clean()
        item_def = cleaned.get("item_definition")
        wage = cleaned.get("fixed_wage_rial")
        if not item_def and wage is None:
            return cleaned  # empty row — skip silently
        if item_def and wage is None:
            self.add_error("fixed_wage_rial", "مبلغ اجرت را وارد کنید.")
        if wage is not None and not item_def:
            self.add_error("item_definition", "آیتم سفارش را انتخاب کنید.")
        return cleaned


class _BaseTechRateFormSet(forms.BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            item_def = form.cleaned_data.get("item_definition")
            if item_def:
                if item_def.pk in seen:
                    raise forms.ValidationError(
                        "آیتم تکراری: یک آیتم سفارش را نمی‌توان چندبار برای یک تکنسین تعریف کرد."
                    )
                seen.add(item_def.pk)


TechnicianRateFormSet = forms.formset_factory(
    TechnicianServiceRateForm,
    formset=_BaseTechRateFormSet,
    extra=3,
    can_delete=True,
)
