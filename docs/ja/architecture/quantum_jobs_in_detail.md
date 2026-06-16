# 量子ジョブの詳細

OQTOPUS は、大きな量子ジョブのペイロードをオブジェクトストレージに保存し、データベースにはジョブのメタデータだけを保存します。
User API、Provider API、ストレージは presigned URL で接続され、クライアントは大きなファイルを API サーバー経由ではなくストレージへ直接アップロードまたはダウンロードします。

このページでは、現在動作しているバックエンド実装と `backend/oas` 配下の OpenAPI を正として仕様を説明します。

## ストレージモデル

各ジョブは、ジョブ ID を名前にしたストレージ prefix を持ちます。

```text
<job_id>/input.zip
<job_id>/combined_program.zip
<job_id>/transpile_result.zip
<job_id>/result.zip
<job_id>/sse_log.zip
```

バックエンドが扱うオブジェクト名は固定です。

| Object | 作成者 | 利用者 | 備考 |
| --- | --- | --- | --- |
| `input.zip` | User | Provider, User | submission 完了前に必須です。ファイル内容は `jobs.S3SubmitJobInfo` に従います。 |
| `combined_program.zip` | Provider | User | `multi_manual` ジョブでのみ受け付けます。 |
| `transpile_result.zip` | Provider | User | transpile 結果です。 |
| `result.zip` | Provider | User | ジョブ結果です。ファイル内容は `jobs.S3JobResult` に従います。 |
| `sse_log.zip` | Provider | User | `sse` ジョブでのみ受け付けます。 |

デフォルトのストレージドライバーは S3 です。
ローカル開発では `local` や `local:minio` も使えますが、API 契約は同じです。API は upload presigned URL data または download presigned URL を返し、クライアントはストレージバックエンドへ直接ファイルを転送します。

各 zip ファイルには、単一の payload ファイルを入れる想定です。現在の実装上の取り決めは次の通りです。

| Object | zip 内エントリ名 | payload format |
| --- | --- | --- |
| `input.zip` | `input.json` | `jobs.S3SubmitJobInfo` に一致する JSON |
| `combined_program.zip` | `combined_program.json` | combined program 用 JSON payload |
| `transpile_result.zip` | `transpile_result.json` | `jobs.S3TranspileResult` に一致する JSON |
| `result.zip` | `result.json` | `jobs.S3JobResult` に一致する JSON |
| `sse_log.zip` | `sse_log.log` | SSE ログ文字列を入れた JSON string payload |

現在の storage-backed 形式では、zip 内エントリ名の規則は基本的に `<object-stem>.json` で、`sse_log.zip` だけ `sse_log.log` を使います。

## User API の流れ

1. `POST /jobs` でジョブを登録します。
   バックエンドは `registered` 状態の DB 行を作成し、生成した `job_id` と `<job_id>/input.zip` 用の upload presigned URL を返します。
2. 返された presigned URL に `input.zip` をアップロードします。
   アップロードするファイルには、`jobs.S3SubmitJobInfo` で表現されるジョブ入力を入れます。
3. `POST /jobs/{job_id}/submit` で submission を完了します。
   request body には `device_id`, `job_type`, `shots` と、任意の transpiler, simulator, mitigation, name, description を含めます。バックエンドは `<job_id>/input.zip` が存在することを確認してから status を `submitted` に変更します。
4. `GET /jobs` または `GET /jobs/{job_id}` でジョブ詳細を取得します。
   submitted 以降のジョブでは、`job_info.input` が download presigned URL になります。Provider が `PATCH /jobs/{job_id}/status` で出力ファイルを報告すると、User API の `job_info` に出力ファイル用 URL が現れます。
5. `DELETE /jobs/{job_id}` で終端状態のジョブを削除します。
   削除できるのは `succeeded`, `failed`, `cancelled` のジョブだけです。バックエンドは DB 行と `<job_id>/` 配下のオブジェクトを削除します。

`registered` ジョブは owner から参照できますが、submission が完了するまで DB 行には未確定フィールドの placeholder が入っています。そのため通常の User API response では `job_id` と `status` だけを返し、明示的に field 指定された未定義項目は `null` になります。

## Provider API の流れ

1. `GET /jobs?device_id=<device_id>` でジョブを poll します。
   `registered` ジョブは返されません。Provider が `submitted` ジョブを取得すると、バックエンドは status を `ready` に進め、`<job_id>/input.zip` の download presigned URL である `input` を返します。
2. 必要に応じて `GET /jobs/{job_id}/upload?items=...` で出力用 upload URL を取得します。
   `items` は `combined_program`, `transpile_result`, `result`, `sse_log` の comma-separated list です。バックエンドは、`multi_manual` 以外の `combined_program` と、`sse` 以外の `sse_log` を拒否します。
3. `{ "status": "running" }` を指定して `PATCH /jobs/{job_id}/status` を呼び、実行開始を反映します。
   この遷移は `ready` からのみ許可されます。
4. presigned URL data を使って出力ファイルをストレージへ直接アップロードします。
5. `PATCH /jobs/{job_id}/status` でジョブを完了します。
   終端状態は `succeeded`, `failed`, `cancelled` です。request body には `execution_time`, `message`, `output_files` を含められます。

`output_files` には `<job_id>/result.zip` のような完全なストレージキーを指定します。
バックエンドは、各キーが対象ジョブに属すること、サポート対象のファイル名であること、ストレージ上に存在することを検証します。
DB にはジョブ ID と `.zip` suffix を除いた正規化済みオブジェクト名を保存し、User API は後でそれらを `job_info` の download URL に展開します。

## 状態遷移

現在の Provider を含む状態遷移は次の通りです。

| From | To | Actor |
| --- | --- | --- |
| `registered` | `submitted` | User API `POST /jobs/{job_id}/submit` |
| `submitted` | `ready` | Provider API `GET /jobs` |
| `ready` | `running` | Provider API `PATCH /jobs/{job_id}/status` |
| `ready` | `failed` | Provider API `PATCH /jobs/{job_id}/status` |
| `running` | `succeeded` | Provider API `PATCH /jobs/{job_id}/status` |
| `running` | `failed` | Provider API `PATCH /jobs/{job_id}/status` |
| `running` | `cancelled` | Provider API `PATCH /jobs/{job_id}/status` |
| `registered`, `submitted`, `ready`, `running` | `cancelled` | User API `POST /jobs/{job_id}/cancel` |

`ready -> failed` は、Provider 側の前処理で失敗したジョブを `running` にする前に報告できるようサポートされています。

## ジョブ入出力スキーマ

`input.zip` には `jobs.S3SubmitJobInfo` に従う payload を入れます。

| Field | Required for | 備考 |
| --- | --- | --- |
| `program` | `sampling`, `estimation`, `multi_manual` | OpenQASM 3 program の配列です。非 multiprogramming job では通常 1 つの program を含みます。 |
| `operator` | `estimation` | Pauli operator item の配列です。 |
| `sse_program` | `sse` | SSE job 用の user program です。 |

Provider の出力は別々の zip ファイルとして保存します。

| File | Schema |
| --- | --- |
| `result.zip` | `jobs.S3JobResult` |
| `transpile_result.zip` | `jobs.S3TranspileResult` |
| `combined_program.zip` | `multi_manual` ジョブ用の combined program |
| `sse_log.zip` | `sse` ジョブ用の SSE log |

アーカイブ構成の例:

```text
<job_id>/input.zip
  input.json

<job_id>/result.zip
  result.json

<job_id>/transpile_result.zip
  transpile_result.json

<job_id>/sse_log.zip
  sse_log.log
```

## 実装メモ

- `jobs.job_info` は DB column ではありません。`jobs` table は metadata, `output_files`, `message` を保存します。
- User API の `job_info` は inline JSON 文字列ではなく、download presigned URL と Provider message を含む response object です。
- upload presigned URL の有効期限は storage strategy に従います。現在の `FSSpecStorage` の default は 1 時間です。
- DB 行の削除後、S3 オブジェクトの cleanup は best-effort で行われます。cleanup に失敗した場合、API は internal server error を返します。
