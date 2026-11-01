"""Track when a note was last updated.

Revision ID: 0002_updated_at
Revises: 0001_initial
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002_updated_at"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	op.add_column(
		"notes",
		sa.Column(
			"updated_at",
			sa.DateTime(timezone=True),
			server_default=sa.func.now(),
			nullable=False,
		),
	)


def downgrade() -> None:
	op.drop_column("notes", "updated_at")
