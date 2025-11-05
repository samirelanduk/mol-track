import getpass
import typer
import keyring

SERVICE_NAME = "moltrack-cli"
USERNAME = "default"

auth_app = typer.Typer(help="Authentication commands (login/logout)")


def save_api_key(api_key: str):
    keyring.set_password(SERVICE_NAME, USERNAME, api_key)


def get_api_key() -> str:
    key = keyring.get_password(SERVICE_NAME, USERNAME)
    if not key:
        raise typer.Exit("❌ No API key found. Please run `login` first.")
    return key


def delete_api_key():
    try:
        keyring.delete_password(SERVICE_NAME, USERNAME)
        typer.echo("✅ API key removed.")
    except keyring.errors.PasswordDeleteError:
        typer.echo("⚠️ No API key found to delete.")


@auth_app.command("login")
def login():
    api_key = getpass.getpass("Enter your API key: ")
    save_api_key(api_key)
    typer.echo("✅ API key saved securely!")


@auth_app.command("logout")
def logout():
    delete_api_key()


@auth_app.command("show")
def show():
    key = get_api_key()
    typer.echo(f"Stored API key: {key}")
