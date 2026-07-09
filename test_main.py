import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import argparse
from pathlib import Path
from datetime import datetime
import logging
import os

import main


class TestQRCodeGenerator(unittest.TestCase):

    def setUp(self):
        logging.root.handlers = []
        logging.basicConfig(level=logging.INFO)

    # ----------------------------------------------------------------------
    # Test create_directory
    # ----------------------------------------------------------------------
    @patch('main.Path.mkdir')
    def test_create_directory_success(self, mock_mkdir):
        main.create_directory(Path('/fake/dir'))
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch('main.Path.mkdir')
    def test_create_directory_failure(self, mock_mkdir):
        mock_mkdir.side_effect = PermissionError("No permission")
        with self.assertRaises(SystemExit) as cm:
            main.create_directory(Path('/fake/dir'))
        self.assertEqual(cm.exception.code, 1)

    # ----------------------------------------------------------------------
    # Test is_valid_url
    # ----------------------------------------------------------------------
    @patch('main.validators.url')
    def test_is_valid_url_valid(self, mock_url):
        mock_url.return_value = True
        self.assertTrue(main.is_valid_url('http://example.com'))
        mock_url.assert_called_once_with('http://example.com')

    @patch('main.validators.url')
    def test_is_valid_url_invalid(self, mock_url):
        mock_url.return_value = False
        self.assertFalse(main.is_valid_url('not_a_url'))
        mock_url.assert_called_once_with('not_a_url')

    # ----------------------------------------------------------------------
    # Test generate_qr_code
    # ----------------------------------------------------------------------
    @patch('pathlib.Path.open', new_callable=mock_open)  # <-- FIXED: mock Path.open
    @patch('main.qrcode.QRCode')
    @patch('main.is_valid_url')
    def test_generate_qr_code_success(self, mock_is_valid, mock_qr_class, mock_path_open):
        mock_is_valid.return_value = True
        mock_qr_instance = MagicMock()
        mock_qr_class.return_value = mock_qr_instance
        mock_img = MagicMock()
        mock_qr_instance.make_image.return_value = mock_img

        path = Path('/fake/qr.png')
        main.generate_qr_code('http://example.com', path, fill_color='blue', back_color='yellow')

        mock_is_valid.assert_called_once_with('http://example.com')
        mock_qr_class.assert_called_once_with(version=1, box_size=10, border=5)
        mock_qr_instance.add_data.assert_called_once_with('http://example.com')
        mock_qr_instance.make.assert_called_once_with(fit=True)
        mock_qr_instance.make_image.assert_called_once_with(fill_color='blue', back_color='yellow')
        mock_path_open.assert_called_once_with(path, 'wb')  # verify Path.open was called
        mock_img.save.assert_called_once_with(mock_path_open.return_value.__enter__.return_value)

    @patch('main.qrcode.QRCode')
    @patch('main.is_valid_url')
    def test_generate_qr_code_invalid_url(self, mock_is_valid, mock_qr_class):
        mock_is_valid.return_value = False
        path = Path('/fake/qr.png')
        main.generate_qr_code('invalid', path)
        mock_is_valid.assert_called_once_with('invalid')
        mock_qr_class.assert_not_called()

    @patch('main.qrcode.QRCode')
    @patch('main.is_valid_url')
    def test_generate_qr_code_exception(self, mock_is_valid, mock_qr_class):
        mock_is_valid.return_value = True
        mock_qr_class.side_effect = Exception("QR generation error")
        with self.assertLogs('root', level='ERROR') as log:
            main.generate_qr_code('http://example.com', Path('/fake/qr.png'))
            self.assertIn("An error occurred while generating or saving the QR code: QR generation error",
                          log.output[0])

    # ----------------------------------------------------------------------
    # Test main()
    # ----------------------------------------------------------------------
    @patch('main.argparse.ArgumentParser.parse_args')
    @patch('main.datetime')
    @patch('main.create_directory')
    @patch('main.generate_qr_code')
    @patch('main.Path.cwd')
    def test_main_defaults_and_env_vars(self, mock_cwd, mock_generate, mock_create_dir, mock_datetime, mock_args):
        # Override module-level variables (they are set at import time)
        main.QR_DIRECTORY = 'test_dir'
        main.FILL_COLOR = 'green'
        main.BACK_COLOR = 'black'

        mock_args.return_value = argparse.Namespace(url='https://github.com/kaw393939')
        mock_cwd.return_value = Path('/fake/cwd')
        fixed_time = datetime(2026, 7, 8, 12, 0, 0)
        mock_datetime.now.return_value = fixed_time
        mock_datetime.strftime = datetime.strftime

        main.main()

        expected_dir = Path('/fake/cwd') / 'test_dir'
        mock_create_dir.assert_called_once_with(expected_dir)
        expected_filename = "QRCode_20260708120000.png"
        expected_path = expected_dir / expected_filename
        mock_generate.assert_called_once_with(
            'https://github.com/kaw393939',
            expected_path,
            fill_color='green',
            back_color='black'
        )

    @patch('main.argparse.ArgumentParser.parse_args')
    @patch('main.create_directory')
    @patch('main.generate_qr_code')
    @patch('main.Path.cwd')
    def test_main_with_custom_url_and_colors(self, mock_cwd, mock_generate, mock_create_dir, mock_args):
        # Override module-level variables for this test
        main.QR_DIRECTORY = 'custom_qr'
        main.FILL_COLOR = 'red'
        main.BACK_COLOR = 'white'

        custom_url = 'https://example.com'
        mock_args.return_value = argparse.Namespace(url=custom_url)
        mock_cwd.return_value = Path('/fake/cwd')
        with patch('main.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 1, 0, 0, 0)
            mock_datetime.strftime = datetime.strftime
            main.main()

        expected_dir = Path('/fake/cwd') / 'custom_qr'
        mock_create_dir.assert_called_once_with(expected_dir)
        expected_path = expected_dir / "QRCode_20260101000000.png"
        mock_generate.assert_called_once_with(
            custom_url,
            expected_path,
            fill_color='red',
            back_color='white'
        )

    @patch('main.argparse.ArgumentParser.parse_args')
    @patch('main.create_directory')
    @patch('main.generate_qr_code')
    @patch('main.Path.cwd')
    def test_main_handles_generate_exception(self, mock_cwd, mock_generate, mock_create_dir, mock_args):
        mock_args.return_value = argparse.Namespace(url='http://example.com')
        mock_cwd.return_value = Path('/fake/cwd')
        with patch.object(main, 'generate_qr_code', wraps=main.generate_qr_code) as wrapped_generate:
            def side_effect(*args, **kwargs):
                logging.error("Simulated error in generate_qr_code")
            wrapped_generate.side_effect = side_effect
            main.main()
            wrapped_generate.assert_called_once()

    # ----------------------------------------------------------------------
    # Test environment variable fallback (via reload)
    # ----------------------------------------------------------------------
    @patch.dict(os.environ, {}, clear=True)
    def test_env_variable_defaults(self):
        import importlib
        import main as main_module
        importlib.reload(main_module)  # re‑evaluate constants from empty environ
        self.assertEqual(main_module.QR_DIRECTORY, 'qr_codes')
        self.assertEqual(main_module.FILL_COLOR, 'red')
        self.assertEqual(main_module.BACK_COLOR, 'white')

    # ----------------------------------------------------------------------
    # Test setup_logging
    # ----------------------------------------------------------------------
    def test_setup_logging(self):
        logging.root.handlers = []
        main.setup_logging()
        self.assertTrue(
            any(isinstance(h, logging.StreamHandler) for h in logging.root.handlers),
            "No StreamHandler found after setup_logging()"
        )


if __name__ == '__main__':
    unittest.main()