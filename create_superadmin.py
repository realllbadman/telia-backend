"""
CLI utilitaire pour gérer les comptes superadmin.

Exemples d'utilisation:
    python create_superadmin.py create-superadmin
    python create_superadmin.py list-superadmins
"""

from __future__ import annotations

import click
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.utils import get_password_hash
from app.database import Base, SessionLocal, engine
from app.models import User, UserRole


def _ensure_schema() -> None:
    """Créer le schéma de base de données lors de l'exécution locale des commandes."""
    Base.metadata.create_all(bind=engine)


def _open_session() -> Session:
    """Fonction utilitaire pour ouvrir une session de base de données avec un nettoyage cohérent."""
    return SessionLocal()


@click.group(help="Commandes de gestion Telia.")
def cli() -> None:
    """Groupe racine CLI."""


@cli.command("create-superadmin", help="Creer un compte superadmin interactif ou via options.")
@click.option("--email", prompt="Email", type=str)
@click.option("--username", prompt="Nom d'utilisateur", type=str)
@click.option("--full-name", prompt="Nom complet", default="", show_default=False)
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Mot de passe du superadmin (min 8 caracteres).",
)
def create_superadmin_command(email: str, username: str, full_name: str, password: str) -> None:
    """Créer un nouvel utilisateur superadmin."""
    full_name = full_name.strip() or None

    if len(password) < 8:
        raise click.ClickException("Le mot de passe doit contenir au moins 8 caracteres.")

    _ensure_schema()
    db = _open_session()

    try:
        email_exists = db.query(User).filter(User.email == email).first()
        if email_exists:
            raise click.ClickException(f"Un utilisateur avec l'email {email} existe deja.")

        username_exists = db.query(User).filter(User.username == username).first()
        if username_exists:
            raise click.ClickException(f"Un utilisateur avec le nom {username} existe deja.")

        hashed_password = get_password_hash(password)
        superadmin = User(
            email=email,
            username=username,
            full_name=full_name,
            hashed_password=hashed_password,
            role=UserRole.SUPERADMIN,
            is_active=True,
        )

        db.add(superadmin)
        db.commit()
        db.refresh(superadmin)

        click.secho("Superadmin crée avec succès", fg="green")
        click.echo(f"ID: {superadmin.id}")
        click.echo(f"Email: {superadmin.email}")
        click.echo(f"Username: {superadmin.username}")
        click.echo(f"Role: {superadmin.role.value}")
    except SQLAlchemyError as exc:
        db.rollback()
        raise click.ClickException(f"Echec de la creation: {exc}") from exc
    finally:
        db.close()


@cli.command("list-superadmins", help="Lister tous les comptes superadmin.")
def list_superadmins_command() -> None:
    """Lister les comptes superadmin existants."""
    _ensure_schema()
    db = _open_session()

    try:
        superadmins = (
            db.query(User)
            .filter(User.role == UserRole.SUPERADMIN)
            .order_by(User.created_at.desc())
            .all()
        )

        if not superadmins:
            click.secho("Aucun superadmin enregistre.", fg="yellow")
            return

        click.secho(f"{len(superadmins)} superadmin(s) trouve(s)", fg="cyan")
        for admin in superadmins:
            status = "Actif" if admin.is_active else "Inactif"
            click.echo("-" * 40)
            click.echo(f"ID: {admin.id}")
            click.echo(f"Username: {admin.username}")
            click.echo(f"Email: {admin.email}")
            click.echo(f"Nom complet: {admin.full_name or 'N/A'}")
            click.echo(f"Statut: {status}")
            click.echo(f"Date de creation: {admin.created_at}")
    except SQLAlchemyError as exc:
        raise click.ClickException(f"Lecture impossible: {exc}") from exc
    finally:
        db.close()


if __name__ == "__main__":
    cli()
