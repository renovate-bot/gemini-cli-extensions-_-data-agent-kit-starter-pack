# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the Dataplex scanner script verification logic."""

import asyncio
import builtins
import json
from unittest import mock

from absl.testing import absltest
from absl.testing import parameterized

from google3.cloud.developer_experience.datacloud_vscode.antigravity.skills.data_autocleaning.scripts import dataplex_scanner


class DataplexScannerTest(parameterized.TestCase, absltest.TestCase):

  @parameterized.named_parameters(
      ("three_parts", "proj.dataset.table"),
      ("four_parts", "proj.catalog.namespace.table"),
  )
  @mock.patch.object(
      dataplex_scanner,
      "run_command_async",
      autospec=True,
  )
  def test_get_table_row_count_success(self, table_id, mock_run_cmd):
    """Test get_table_row_count successfully parses BQ output."""
    mock_run_cmd.return_value = '[{"count": "100"}]'

    count = asyncio.run(dataplex_scanner.get_table_row_count(table_id))

    self.assertEqual(count, 100)
    mock_run_cmd.assert_called_once_with(
        "bq query --quiet --nouse_legacy_sql --format=json "
        f"'SELECT count(*) as count FROM `{table_id}`'"
    )

  @mock.patch.object(
      dataplex_scanner,
      "run_command_async",
      autospec=True,
  )
  def test_get_table_row_count_failure(self, mock_run_cmd):
    """Test get_table_row_count toggles error on command failure."""
    mock_run_cmd.side_effect = RuntimeError("Command failed")

    with self.assertRaisesRegex(RuntimeError, "Command failed"):
      asyncio.run(dataplex_scanner.get_table_row_count("proj.dataset.table"))

  @mock.patch.object(
      dataplex_scanner,
      "get_table_row_count",
      autospec=True,
  )
  @mock.patch.object(
      dataplex_scanner,
      "run_command_async",
      autospec=True,
  )
  def test_create_and_wait_for_scan_empty_table(
      self, mock_run_cmd, mock_get_count
  ):
    """Test create_and_wait_for_scan skips empty tables."""
    mock_get_count.return_value = 0

    asyncio.run(
        dataplex_scanner.create_and_wait_for_scan(
            "proj.dataset.table", "us-central1", self.create_tempdir().full_path
        )
    )

    # Should not invoke gcloud datascans
    mock_run_cmd.assert_not_called()

  @parameterized.named_parameters(
      ("two_parts", "invalid.id"),
      ("five_parts", "proj.catalog.namespace.table.suffix"),
  )
  @mock.patch.object(
      dataplex_scanner,
      "get_table_row_count",
      autospec=True,
  )
  @mock.patch.object(
      dataplex_scanner,
      "run_command_async",
      autospec=True,
  )
  def test_create_and_wait_for_scan_invalid_id(
      self, table_id, mock_run_cmd, mock_get_count
  ):
    """Test create_and_wait_for_scan skips invalid table IDs."""
    asyncio.run(
        dataplex_scanner.create_and_wait_for_scan(
            table_id, "us-central1", self.create_tempdir().full_path
        )
    )

    mock_get_count.assert_not_called()
    mock_run_cmd.assert_not_called()

  @mock.patch.object(
      dataplex_scanner,
      "get_table_row_count",
      autospec=True,
  )
  @mock.patch.object(
      dataplex_scanner,
      "run_command_async",
      autospec=True,
  )
  @mock.patch.object(builtins, "open", new_callable=mock.mock_open)
  @mock.patch(
      "google3.cloud.developer_experience.datacloud_vscode.antigravity.skills.data_autocleaning.scripts.dataplex_scanner.uuid.uuid4"
  )
  def test_create_and_wait_for_scan_success(
      self, mock_uuid, mock_open, mock_run_cmd, mock_get_count
  ):
    """Test create_and_wait_for_scan successfully polls and writes result."""
    mock_uuid.return_value.hex = "12345678123456781234567812345678"
    mock_get_count.return_value = 100

    # Mock sequence: 1. create logic return value, 2. describe scan return value
    mock_run_cmd.side_effect = [
        "{}",  # create scan output
        json.dumps(
            {"dataProfileResult": {"profile": {}}}
        ),  # describe scan output
    ]

    asyncio.run(
        dataplex_scanner.create_and_wait_for_scan(
            "proj.dataset.table", "us-central1", self.create_tempdir().full_path
        )
    )

    expected_create_cmd = (
        "gcloud dataplex datascans create data-profile data-profile-12345678"
        " --location=us-central1"
        ' --data-source-resource="//bigquery.googleapis.com/projects/proj/datasets/dataset/tables/table"'
        ' --project=proj --one-time --ttl-after-scan-completion="2400s"'
        " --format=json"
    )
    expected_describe_cmd = (
        "gcloud dataplex datascans describe data-profile-12345678 "
        "--location=us-central1 "
        "--project=proj "
        "--view=full "
        "--format=json"
    )

    mock_run_cmd.assert_has_calls([
        mock.call(expected_create_cmd),
        mock.call(expected_describe_cmd),
    ])
    mock_open.assert_called_once()

  @mock.patch.object(
      dataplex_scanner,
      "get_table_row_count",
      autospec=True,
  )
  @mock.patch.object(
      dataplex_scanner,
      "run_command_async",
      autospec=True,
  )
  @mock.patch.object(builtins, "open", new_callable=mock.mock_open)
  @mock.patch(
      "google3.cloud.developer_experience.datacloud_vscode.antigravity.skills.data_autocleaning.scripts.dataplex_scanner.uuid.uuid4"
  )
  def test_create_and_wait_for_scan_success_biglake(
      self, mock_uuid, mock_open, mock_run_cmd, mock_get_count
  ):
    mock_uuid.return_value.hex = "12345678123456781234567812345678"
    mock_get_count.return_value = 100

    mock_run_cmd.side_effect = [
        "{}",  # create scan output
        json.dumps(
            {"dataProfileResult": {"profile": {}}}
        ),  # describe scan output
    ]

    asyncio.run(
        dataplex_scanner.create_and_wait_for_scan(
            "proj.catalog.namespace.table",
            "us-central1",
            self.create_tempdir().full_path,
        )
    )

    expected_create_cmd = (
        "gcloud dataplex datascans create data-profile data-profile-12345678"
        " --location=us-central1"
        ' --data-source-resource="//biglake.googleapis.com/iceberg/v1/restcatalog/v1/projects/proj/catalogs/catalog/namespaces/namespace/tables/table"'
        ' --project=proj --one-time --ttl-after-scan-completion="2400s"'
        " --format=json"
    )
    expected_describe_cmd = (
        "gcloud dataplex datascans describe data-profile-12345678 "
        "--location=us-central1 "
        "--project=proj "
        "--view=full "
        "--format=json"
    )

    mock_run_cmd.assert_has_calls([
        mock.call(expected_create_cmd),
        mock.call(expected_describe_cmd),
    ])
    mock_open.assert_called_once()

  @mock.patch.object(
      dataplex_scanner,
      "get_table_row_count",
      autospec=True,
  )
  @mock.patch.object(
      dataplex_scanner,
      "run_command_async",
      autospec=True,
  )
  @mock.patch.object(builtins, "open", new_callable=mock.mock_open)
  @mock.patch(
      "google3.cloud.developer_experience.datacloud_vscode.antigravity.skills.data_autocleaning.scripts.dataplex_scanner.uuid.uuid4"
  )
  def test_create_and_wait_for_scan_partial_polling(
      self, mock_uuid, mock_open, mock_run_cmd, mock_get_count
  ):
    """Test create_and_wait_for_scan continues polling if profile is missing."""
    mock_uuid.return_value.hex = "12345678123456781234567812345678"
    mock_get_count.return_value = 100

    # Mock sequence: 1. create scan, 2. describe (partial), 3. describe (full)
    mock_run_cmd.side_effect = [
        "{}",  # create scan output
        json.dumps({"dataProfileResult": {}}),  # partial: profile missing
        json.dumps({"dataProfileResult": {"profile": {}}}),  # full results
    ]

    asyncio.run(
        dataplex_scanner.create_and_wait_for_scan(
            "proj.dataset.table", "us-central1", self.create_tempdir().full_path
        )
    )

    expected_create_cmd = (
        "gcloud dataplex datascans create data-profile data-profile-12345678"
        " --location=us-central1"
        ' --data-source-resource="//bigquery.googleapis.com/projects/proj/datasets/dataset/tables/table"'
        ' --project=proj --one-time --ttl-after-scan-completion="2400s"'
        " --format=json"
    )
    expected_describe_cmd = (
        "gcloud dataplex datascans describe data-profile-12345678 "
        "--location=us-central1 "
        "--project=proj "
        "--view=full "
        "--format=json"
    )

    mock_run_cmd.assert_has_calls([
        mock.call(expected_create_cmd),
        mock.call(expected_describe_cmd),
        mock.call(expected_describe_cmd),
    ])
    mock_open.assert_called_once()


if __name__ == "__main__":
  absltest.main()
