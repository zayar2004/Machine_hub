"""Auth forms."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo


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
    """Simplified registration — Name + Password only."""
    name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(min=2, max=120)],
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
