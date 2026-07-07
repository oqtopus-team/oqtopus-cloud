# デバイス情報の詳細

OQTOPUS は device_info の実体をオブジェクトストレージに保存し、API では inline JSON ではなく presigned URL 経由で参照します。
データベースには `device_type`, `status`, `n_qubits`, `calibrated_at` などのデバイスメタデータを保持し、実際の `device_info` payload はストレージ上の archive に置きます。

このページでは、現在動作しているバックエンドの挙動と、周辺クライアントで使われているストレージ上の慣例を説明します。内容は `backend/oas` 配下の OpenAPI と実装に沿っています。

## ストレージモデル

各デバイスは、決定的な storage key を 1 つ持ちます。

```text
devices/<device_id>/device_info.zip
```

オブジェクトキーはバックエンドで固定されています。クライアントは慣例として `device_info.json` を 1 つだけ含む zip をアップロードしますが、バックエンドが検証するのはオブジェクトキーであり、archive 内のファイル名ではありません。

| Object | 慣例上の zip 内エントリ名 | 作成者 | 利用者 | payload format | 備考 |
| --- | --- | --- | --- | --- | --- |
| `devices/<device_id>/device_info.zip` | `device_info.json` | Admin client, Provider, Engine | Admin, User, SDK | デバイス JSON payload | 現在 storage-backed なデバイス payload はこれだけです。 |

デフォルトのストレージドライバーは S3 です。
ローカル開発では `local` や `local:minio` も使えますが、API 契約は同じです。API は upload presigned URL data または download presigned URL を返し、クライアントは archive をストレージバックエンドへ直接転送します。

OpenAPI レベルでは、`device_info.zip` の中身の payload format は構造化 schema としては規定されていません。Admin 側の request model では `device_info` を JSON 文字列として扱い、read 側 API では `device_info` を presigned download URL を入れた文字列 field として返します。

## 読み出しモデル

Admin API と User API の `GET /devices` および `GET /devices/{device_id}` は、`devices/<device_id>/device_info.zip` が存在するときだけ `device_info` に download presigned URL を返します。
オブジェクトが存在しない場合、device row 自体が存在していても `device_info` は `null` になります。

バックエンドは storage key を `devices` table に保存しません。毎回 `device_id` から `devices/<device_id>/device_info.zip` を組み立てて参照します。

## Admin API の流れ

現在の Admin API は、storage-backed な 2 段階フローです。

1. DB 上の device row を登録または更新します。
   `POST /devices` は row を作成し、`PATCH /devices/{device_id}` は `status`, `n_qubits`, `description` などの DB-backed metadata を更新します。
2. `GET /devices/{device_id}/device_info/upload` で upload 先を取得します。
   バックエンドは `devices/<device_id>/device_info.zip` 用の presigned URL data を返します。
3. `device_info.zip` をストレージへ直接アップロードします。
4. 必要なら `PATCH /devices/{device_id}` で `calibrated_at` や `description` など残りの DB-backed metadata だけを更新します。
   `device_info.zip` 自体は upload が完了した時点で以後の read の source of truth になるため、admin client は `device_info` を PATCH body に載せ直す必要はありません。

現在の admin frontend は、先に `device_info.zip` を upload し、その後に必要な DB-backed field だけを PATCH します。

後方互換のため、`POST /devices` は request body 中の inline `device_info` JSON から `device_id` を抽出し続けます。ただし、その inline JSON 自体は読み出しモデルの source of truth として保存されません。登録後の API response が返す `device_info` は、常に storage-backed object の URL です。

更新シーケンス自体は短いですが、最後に使う API は Admin フローと Provider / Engine フローで異なります。

```mermaid
sequenceDiagram
   participant Client as Admin または Engine
   participant API as Cloud API
   participant Storage as Object Storage

   Client->>API: GET /devices/{id}/device_info/upload
   API-->>Client: presigned upload URL data
   Client->>Storage: device_info.zip を upload
   alt Admin フロー
      Client->>API: PATCH /devices/{id} with remaining DB fields only
   else Provider / Engine フロー
      Client->>API: PATCH /devices/{id}/device_info with calibrated_at
   end
   API-->>Client: update accepted
```

## Provider / Engine の流れ

Provider 側の upload も同じ storage convention を使いますが、確定用 endpoint は専用です。

1. Provider API の `GET /devices/{device_id}/device_info/upload` で upload 先を取得します。
2. `device_info.zip` をストレージへ直接アップロードします。
3. `PATCH /devices/{device_id}/device_info` に `calibrated_at` を渡して upload を確定します。

engine はこの flow を provider API 経由で使います。起動時に `DeviceGatewayFetcher` が device gateway から初回 fetch を行い、device repository update sequence を呼びます。device_info update が有効な場合、repository は次の順で処理します。

1. presigned upload 先を取得する
2. `devices/<device_id>/device_info.zip` を upload する
3. `PATCH /devices/{device_id}/device_info` に `calibrated_at` を渡す

起動後も、fetch した `device_info` payload または `calibrated_at` が変化したときに、同じ upload flow が再実行されます。

## 上書きと削除のセマンティクス

storage key は決定的なので、同じ `device_id` に対して新しい archive を upload すると前のオブジェクトを上書きします。最後に成功した upload が新しい source of truth になります。

Admin API の `DELETE /devices/{device_id}` は、次の両方を削除します。

- `devices` table の DB row
- 存在すれば `devices/<device_id>/device_info.zip` オブジェクト

これにより、device cleanup 時に孤立したストレージオブジェクトを残しません。

## アーカイブ構成の例

```text
devices/qulacs/device_info.zip
  device_info.json
```

## 実装メモ

- read 時の `device_info` は storage-backed です。API response は raw JSON ではなく download presigned URL を返します。
- OpenAPI では `device_info` 自体の型付き schema は定義していません。write 側の契約は実質的に「JSON を文字列化して渡す」、read 側の契約は「archive payload を指す URL 文字列を返す」です。
- Admin API の PATCH 契約は metadata 更新専用です。現在の admin client は `device_info.zip` を別途 upload し、`PATCH /devices/{device_id}` に `device_info` を載せ直しません。
- `calibrated_at` は引き続き `devices` table に保存され、オブジェクト upload 確定とは別に更新されます。
- upload presigned URL の有効期限は storage strategy に従います。現在の `FSSpecStorage` default は 1 時間です。
- バックエンドが検証するのは `device_info.zip` の存在であり、archive 内の entry 名ではありません。
- device row を再作成しても `device_info.zip` は復元されません。object を戻すには provider/admin の upload か、engine の起動時同期が必要です。
