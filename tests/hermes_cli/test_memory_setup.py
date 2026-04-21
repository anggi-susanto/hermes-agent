from argparse import Namespace
from unittest.mock import patch


class TestMemoryMigrationCli:
    def test_memory_command_routes_migrate_subcommand(self):
        from hermes_cli import memory_setup

        args = Namespace(memory_command="migrate", migrate_action="audit")

        with patch.object(memory_setup, "cmd_migrate") as mock_cmd:
            memory_setup.memory_command(args)

        mock_cmd.assert_called_once_with(args)

    def test_cmd_migrate_audit_calls_active_letta_provider(self, capsys):
        from hermes_cli import memory_setup

        provider = type("Provider", (), {})()
        provider.audit_state_db_history_migration = lambda db_path, **kwargs: {
            "target_canonical_user_id": kwargs["target_canonical_user_id"],
            "expected_unique_keys": 12,
            "duplicate_existing_rows": 3,
            "db_path": db_path,
        }

        args = Namespace(
            migrate_action="audit",
            state_db="/tmp/state.db",
            user_id="owner:73784266",
            sources="telegram,cli",
            json=False,
        )

        with (
            patch("hermes_cli.memory_setup.load_config", return_value={"memory": {"provider": "letta"}}),
            patch("hermes_cli.memory_setup.load_memory_provider", return_value=provider),
        ):
            memory_setup.cmd_migrate(args)

        out = capsys.readouterr().out
        assert "Letta migration audit" in out
        assert "expected_unique_keys: 12" in out
        assert "duplicate_existing_rows: 3" in out

    def test_cmd_migrate_cleanup_uses_provider_and_emits_json(self, capsys):
        from hermes_cli import memory_setup

        provider = type("Provider", (), {})()
        provider.cleanup_migrated_history_duplicates = lambda **kwargs: {
            "deleted_rows": 9,
            "duplicate_groups": 4,
            "target_canonical_user_id": kwargs["target_canonical_user_id"],
        }

        args = Namespace(
            migrate_action="cleanup",
            state_db="/tmp/state.db",
            user_id="owner:73784266",
            sources="telegram,cli",
            json=True,
        )

        with (
            patch("hermes_cli.memory_setup.load_config", return_value={"memory": {"provider": "letta"}}),
            patch("hermes_cli.memory_setup.load_memory_provider", return_value=provider),
        ):
            memory_setup.cmd_migrate(args)

        out = capsys.readouterr().out
        assert '"deleted_rows": 9' in out

    def test_cmd_migrate_requires_active_letta_provider(self, capsys):
        from hermes_cli import memory_setup

        args = Namespace(
            migrate_action="resume",
            state_db="/tmp/state.db",
            user_id="owner:73784266",
            sources="telegram,cli",
            json=False,
        )

        with patch("hermes_cli.memory_setup.load_config", return_value={"memory": {"provider": "honcho"}}):
            memory_setup.cmd_migrate(args)

        out = capsys.readouterr().out
        assert "Letta must be the active memory provider" in out
