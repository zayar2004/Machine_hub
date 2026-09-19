"""Machine Hub entry point."""
import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

app = create_app()


@app.shell_context_processor
def _shell_context():
    """Make `db` and all models available in `flask shell`."""
    from app import models as m
    return {
        "db": db,
        "Shop": m.Shop,
        "User": m.User,
        "Machine": m.Machine,
        "Error": m.Error,
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(host=host, port=port, debug=debug)
