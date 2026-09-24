"""Auth forms."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, Regexp, ValidationError


class LoginForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=60)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=4, max=200)],
    )
    remember_me = BooleanField("Remember me", default=True)
    submit = SubmitField("Sign in")


class RegisterForm(FlaskForm):
    """Registration — Name + Username + Password."""
    name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(min=2, max=120)],
    )
    username = StringField(
        "Username (login အတွက်)",
        validators=[
            DataRequired(),
            Length(min=3, max=30,
                   message="Username ၃-၃၀ လုံး ရှိရမယ်"),
            Regexp(
                r"^[a-zA-Z0-9_]+$",
                message="Letters, numbers, underscore (_) ပဲ ရပါတယ်",
            ),
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
    submit = SubmitField("Create Account")

    def validate_username(self, field):
        """Check username uniqueness (lowercase)."""
        from ..models import User
        username = (field.data or "").strip().lower()
        if User.query.filter_by(username=username).first():
            raise ValidationError(
                "ဒီ username ရှိပြီးသား — တခြား သုံးပါ"
            )
