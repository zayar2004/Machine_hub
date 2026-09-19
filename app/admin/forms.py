"""Admin forms."""
from flask_wtf import FlaskForm
from wtforms import (
    SelectMultipleField,
    StringField, PasswordField, SelectField, SubmitField, HiddenField,
    FileField, IntegerField,
)
from wtforms.fields import MultipleFileField
from wtforms.validators import (
    DataRequired, Length, Regexp, EqualTo, Optional,
)


class ShopForm(FlaskForm):
    """Create / edit shop."""
    shop_code = StringField(
        "Shop Code",
        validators=[
            DataRequired(),
            Length(min=1, max=20),
            Regexp(r"^[A-Za-z0-9_\-]+$",
                   message="Only letters, digits, underscore, dash allowed."),
        ],
    )
    shop_name = StringField(
        "Shop Name",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    status = SelectField(
        "Status (အခြေအနေ)",
        choices=[
            ("ACTIVE", "Active"),
            ("INACTIVE", "Inactive"),
            ("ARCHIVED", "Archived"),
        ],
        default="ACTIVE",
    )
    submit = SubmitField("Save")


class UserCreateForm(FlaskForm):
    """Create a new user."""
    name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=60),
            Regexp(r"^[A-Za-z0-9_.\-]+$",
                   message="Only letters, digits, dot, underscore, dash allowed."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=200)],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    role = SelectField(
        "Role",
        choices=[("USER", "User"), ("ADMIN", "Admin")],
        default="USER",
    )
    shop_id = SelectField(
        "Shop",
        coerce=int,
        choices=[],  # populated in route
        validators=[Optional()],
    )
    status = SelectField(
        "Status",
        choices=[
            ("ACTIVE", "Active"),
            ("INACTIVE", "Inactive"),
        ],
        default="ACTIVE",
    )
    submit = SubmitField("Create User")


class UserEditForm(FlaskForm):
    """Edit an existing user (no password change here)."""
    name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=60),
            Regexp(r"^[A-Za-z0-9_.\-]+$",
                   message="Only letters, digits, dot, underscore, dash allowed."),
        ],
    )
    role = SelectField(
        "Role",
        choices=[("USER", "User"), ("ADMIN", "Admin")],
    )
    shop_id = SelectField(
        "Shop",
        coerce=int,
        choices=[],
        validators=[Optional()],
    )
    status = SelectField(
        "Status",
        choices=[
            ("ACTIVE", "Active"),
            ("INACTIVE", "Inactive"),
            ("ARCHIVED", "Archived"),
        ],
    )
    submit = SubmitField("Save Changes")


class PasswordResetForm(FlaskForm):
    """Reset a user's password."""
    user_id = HiddenField()
    new_password = PasswordField(
        "New Password",
        validators=[DataRequired(), Length(min=6, max=200)],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="Passwords must match."),
        ],
    )
    submit = SubmitField("Reset Password")


class MachineForm(FlaskForm):
    """Create / edit machine."""
    shop_id = SelectField(
        "Shop",
        coerce=int,
        choices=[],  # populated in route
        validators=[DataRequired(message="Shop is required.")],
    )
    machine_name = StringField(
        "Machine Name",
        validators=[DataRequired(), Length(min=1, max=160)],
    )
    machine_code = StringField(
        "Machine Code",
        validators=[
            DataRequired(),
            Length(min=1, max=60),
            Regexp(r"^[A-Za-z0-9_\-]+$",
                   message="Only letters, digits, underscore, dash allowed."),
        ],
    )
    description = StringField(
        "Description (optional)",
        validators=[Optional(), Length(max=500)],
    )
    status = SelectField(
        "Status",
        choices=[
            ("ACTIVE", "Active"),
            ("INACTIVE", "Inactive"),
            ("ARCHIVED", "Archived"),
        ],
        default="ACTIVE",
    )
    submit = SubmitField("Save")


class ErrorForm(FlaskForm):
    """Create / edit global error knowledge."""
    error_code = StringField(
        "Error Code (အမှားကုဒ်)",
        validators=[
            DataRequired(),
            Length(min=1, max=60),
            Regexp(r"^[A-Za-z0-9_\-\. ]+$",
                   message="Only letters, digits, space, dot, underscore, dash allowed."),
        ],
    )
    error_name = StringField(
        "Error Name (အမှားအမည်)",
        validators=[DataRequired(), Length(min=2, max=200)],
    )
    error_fix = StringField(
        "Fix / Solution (ဖြေရှင်းနည်း — မထည့်လည်းရ)",
        validators=[Optional(), Length(max=2000)],
    )
    explanation = StringField(
        "Explanation (ရှင်းလင်းချက် — မထည့်လည်းရ)",
        validators=[Optional(), Length(max=2000)],
    )
    machine_name = StringField(
        "Machine Name / Keyword (စက်အမည်/စကားလုံး — မထည့်လည်းရ)",
        validators=[Optional(), Length(max=200)],
        description=(
            "ဒီ error က ဘယ် machine တွေအတွက်? "
            "Full name, partial, or keyword — ဘယ်လိုထည့်ထည်း ရပါတယ်. "
            "User က ရှာတဲ့အခါ auto-match ဖြစ်လာမယ်."
        ),
    )
    # Machine linking — handled via custom UI (see template)
    # We read 'machines' from request.form directly in the route
    # Photos
    photos = MultipleFileField(
        "Photos (ဓာတ်ပုံများ — မထည့်လည်းရ)",
        validators=[Optional()],
    )
    photo_caption = StringField(
        "Photo Caption (ဓာတ်ပုံ ဖော်ပြချက် — မထည့်လည်းရ)",
        validators=[Optional(), Length(max=200)],
    )
    category = SelectField(
        "အမျိုးအစား",
        choices=[
            ("ERROR", "⚠️ Error — ပျက်စီး/ချို့ယွင်း"),
            ("TIP", "💡 Tip — အသုံးဝင်တဲ့ အကြံပြုချက်"),
            ("INFO", "ℹ️ Info — အချက်အလက်"),
            ("HOW_TO", "📖 How-To — အဆင့်ဆင့် လမ်းညွှန်"),
        ],
        default="ERROR",
    )
    status = SelectField(
        "Status",
        choices=[
            ("ACTIVE", "Active"),
            ("INACTIVE", "Inactive"),
            ("ARCHIVED", "Archived"),
        ],
        default="ACTIVE",
    )
    submit = SubmitField("Save")


class MachineLinkForm(FlaskForm):
    """Attach an error to a machine."""
    machine_id = SelectField(
        "Add Machine",
        coerce=int,
        choices=[],  # populated in route
        validators=[DataRequired()],
    )
    submit = SubmitField("Link")


class ErrorLinkForm(FlaskForm):
    """Attach a machine to an error."""
    error_id = SelectField(
        "Add Error",
        coerce=int,
        choices=[],  # populated in route
        validators=[DataRequired()],
    )
    submit = SubmitField("Link")


class MachineImportUploadForm(FlaskForm):
    """Step 1 — upload machine Excel + pick shop."""
    shop_id = SelectField(
        "Shop (applies to all imported machines)",
        coerce=int,
        choices=[],  # populated in route
        validators=[DataRequired()],
    )
    import_mode = SelectField(
        "If machine code already exists:",
        choices=[
            ("update", "Update — overwrite existing (empty cells kept)"),
            ("skip", "Skip — keep existing, only add new"),
            ("error", "Error — reject if duplicate"),
        ],
        default="update",
    )
    excel_file = FileField(
        "Excel File (.xlsx)",
        validators=[DataRequired()],
    )
    submit = SubmitField("Preview")


class ErrorImportUploadForm(FlaskForm):
    """Step 1 — upload error Excel."""
    import_mode = SelectField(
        "If error code already exists:",
        choices=[
            ("update", "Update — overwrite existing"),
            ("skip", "Skip — keep existing, only add new"),
            ("error", "Error — reject if duplicate"),
        ],
        default="update",
    )
    excel_file = FileField(
        "Excel File (.xlsx)",
        validators=[DataRequired()],
    )
    submit = SubmitField("Preview")


class ConfirmImportForm(FlaskForm):
    """Step 2 — confirm import."""
    confirm = SubmitField("Import Now")


class PhotoUploadForm(FlaskForm):
    """Upload one or more photos to an error."""
    images = MultipleFileField(
        "Photos (JPG / PNG / WEBP)",
        validators=[DataRequired()],
    )
    caption = StringField(
        "Caption (optional, applies to all in this upload)",
        validators=[Optional(), Length(max=200)],
    )
    submit = SubmitField("Upload")


class PhotoEditForm(FlaskForm):
    """Edit a single photo's caption + sort order."""
    caption = StringField(
        "Caption",
        validators=[Optional(), Length(max=200)],
    )
    sort_order = IntegerField(
        "Sort Order",
        default=0,
        validators=[Optional()],
    )
    submit = SubmitField("သိမ်းဆည်းမည်")


class RepairHistoryForm(FlaskForm):
    """Add a repair history entry to a machine."""
    error_id = SelectField(
        "Related Error (optional)",
        coerce=int,
        choices=[],  # populated in route
        validators=[Optional()],
    )
    repaired_at = StringField(
        "Repaired At (YYYY-MM-DD HH:MM, optional)",
        validators=[Optional(), Length(max=40)],
    )
    description = StringField(
        "Description",
        validators=[DataRequired(), Length(min=2, max=500)],
    )
    notes = StringField(
        "Notes (optional)",
        validators=[Optional(), Length(max=2000)],
    )
    submit = SubmitField("Add Repair Entry")
