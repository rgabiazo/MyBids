from types import SimpleNamespace, ModuleType
import sys

# Stub external dependencies imported during cli initialisation
sys.modules.setdefault('tableprint', ModuleType('tableprint'))
ruamel_mod = ModuleType('ruamel')
ruamel_yaml_mod = ModuleType('ruamel.yaml')
class DummyYAML:
    def load(self, *args, **kwargs):
        return {}
ruamel_yaml_mod.YAML = DummyYAML
sys.modules['ruamel'] = ruamel_mod
sys.modules['ruamel.yaml'] = ruamel_yaml_mod

from click.testing import CliRunner
import dicomatic.cli as cli


def test_cli_option_merge(monkeypatch, tmp_path):
    captured = {}

    def fake_load_config(path):
        return SimpleNamespace(
            dicom=SimpleNamespace(server='', port='', tls='', username='', password=''),
            session_map={},
            bids=SimpleNamespace(root=''),
        )

    def fake_auth(cfg):
        captured['cfg'] = cfg

    monkeypatch.setattr(cli, 'load_config', fake_load_config)
    monkeypatch.setattr(cli, 'ensure_authenticated', fake_auth)
    monkeypatch.setattr(cli, '_interactive_menu', lambda ctx: None)
    monkeypatch.setenv('DICOM_USERNAME', 'env_user')

    runner = CliRunner()
    cfg_file = tmp_path / 'cfg.yml'
    cfg_file.write_text('dummy: true')

    result = runner.invoke(
        cli.cli,
        [
            '--config', str(cfg_file),
            '--server', 'HOST',
            '--port', '1234',
            '--tls', 'ssl',
            '--bids-root', str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    cfg = captured['cfg']
    assert cfg.dicom.server == 'HOST'
    assert cfg.dicom.port == '1234'
    assert cfg.dicom.tls == 'ssl'
    assert cfg.dicom.username == 'env_user'
    assert cfg.bids.root == str(tmp_path)
