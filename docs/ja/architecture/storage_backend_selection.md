# ストレージバックエンドの選定

OQTOPUS は大きなジョブペイロードをオブジェクトストレージに保存します (格納形式や API との関係は [量子ジョブの詳細](quantum_jobs_in_detail.md) を参照)。AWS 上ではデフォルトの `s3` ドライバを使いますが、オンプレ環境やローカル開発では自前の S3 互換ストレージを使います。

SeaweedFS をローカル環境の既定バックエンドとして追加します。`local:minio` は将来的に廃止する方針で、SeaweedFS への移行期間中は既存ドライバとその設定を非推奨警告付きで維持します。このページでは選定の経緯、設定、リリース時の互換性確認を説明します。

## 選定基準

以前は MinIO を使っていましたが、2026 年に MinIO の OSS 版が実質終了した (Community Edition から管理 UI が剥奪され、ビルド済み Docker イメージの配布も停止、最終的にアーカイブ) ため、置き換えが必要になりました。次の条件で候補を比較しています。

1. S3 互換 API があること (list/get/put/presigned URL での upload/download)
2. 1台のサーバで始められて、クラスタ運用にも対応している
3. 管理用の Web UI がある
4. 公式の Docker イメージが提供されている
5. コミュニティ・開発がアクティブでオープン (MinIO のようにならない)
6. プロダクショングレード (本番運用に耐えられるか)

前提として無料であること。

| 候補 | ①S3互換 | ②単一→クラスタ | ③Web UI | ④公式Docker | ⑤活発なOSS (主体) | ⑥本番実績 | ローカル確認 | 無料 | 総合 |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | --- |
| **[SeaweedFS](https://github.com/seaweedfs/seaweedfs)** | ○ | ○ | ○ | ○ | △ 個人 (Chris Lu 氏) | ○ 実績あり | ○ | ○ | **◎ 採用** |
| [RustFS](https://github.com/rustfs/rustfs) | ○ | △ | ○ | ○ | △ 企業 (RustFS Inc.、若い) | △ まだ beta | ○ | ○ | ○ 今回は見送り (実力は高いが `v1.0.0-beta.12` 時点でまだ beta、クラスタ対応も始まったばかり) |
| [Garage](https://garagehq.deuxfleurs.fr/) | ○ | ○ | × | ○ | ◎ 非営利団体 (Deuxfleurs) | ○ | - 未検証 | ○ | ○ 補欠 (Web UI 無し) |
| [Ceph (RGW)](https://docs.ceph.com/en/latest/radosgw/) | ◎ | × | ○ | ○ | ◎ 大企業複数 (Red Hat/IBM/SUSE) | ◎ | - 未検証 | ○ | △ オーバースペック (最低3ノード必須) |
| [Cloudflare R2](https://developers.cloudflare.com/r2/) | ○ | - | - | - | - | - | - | - | ✕ 対象外 (オンプレ不可、Cloudflare 上でのみ動くマネージドサービス) |
| ~~[MinIO](https://github.com/minio/minio)~~ | ○ | ○ | ~~×~~ | ~~×~~ | ~~× 企業 (MinIO Inc.、方針転換)~~ | ○ | - | ~~△~~ | ✕ 対象外 (2026年にアーカイブ) |

SeaweedFS も中心開発者が個人であるため、⑤の単一主体リスクは残ります。それでも実績・機能の広さとローカル検証の結果で他候補に優ったため採用しました。

## seaweedfs ドライバ

`seaweedfs` ドライバは [SeaweedFS](https://github.com/seaweedfs/seaweedfs) にオブジェクトを格納します。ローカル開発では `backend/compose.yaml` が起動し、オンプレ環境では AWS S3 の代わりに SeaweedFS を運用します。

`FSSpecStorage` は SeaweedFS へ AWS S3 と同じ S3 コードパスで接続します。SeaweedFS の空ディレクトリがオブジェクトのキーとして返らないよう、prefix の結果からディレクトリマーカーを除外しています。認証情報・接続先は `backend/compose.yaml` の `STORAGE_SEAWEEDFS_BUCKET_NAME` / `STORAGE_SEAWEEDFS_USERNAME` / `STORAGE_SEAWEEDFS_PASSWORD` / `STORAGE_SEAWEEDFS_ENDPOINT_URL` で設定します。S3 互換のバックエンドであれば同じコードパスで接続できるため、将来別の実装へ乗り換える場合も変更は接続設定だけで済みます。ドライバ名は本プロジェクトが実際に運用・検証しているバックエンドを表すもので、実装に SeaweedFS 固有の要素はありません。RustFS など他のセルフホスト S3 互換バックエンドを使う場合も、`STORAGE_SEAWEEDFS_ENDPOINT_URL` と認証情報の向き先を変えるだけで接続できます。

### `local:minio` からの移行

`local:minio` ドライバは deprecated ですが、これまで通り動作します。設定の読み方は従来のままで、使用時に警告ログを出力します。移行するには `STORAGE_DRIVER` を `seaweedfs` に変更し、`STORAGE_LOCAL_MINIO_*` の設定を `STORAGE_SEAWEEDFS_*` に置き換えてください。Terraform では `storage_env_vars_local_minio` が `storage_env_vars_seaweedfs` になります。

`local:minio` は将来的に廃止する方針ですが、廃止時期は未定です。既存デプロイの SeaweedFS への移行状況を考慮して時期を判断します。SeaweedFS の互換性テストが通っても、それだけで削除可能になったり、利用者の移行が完了したりするわけではありません。

### 非推奨の MinIO スタックをローカルで起動する

`backend/compose.yaml` には MinIO のサービスが compose profile 付きで残してあります。明示的に指定しない限り起動しません。既存設定で起動できる状態を維持し、ドライバのサポート期間中に回帰テストと互換性確認を行うための構成です。

```bash
cd backend
make up STORAGE_STACK=minio                   # MySQL + MinIO、マイグレーションとシード
make run-user STORAGE_STACK=minio             # この構成で API を起動
make check-presigned-post STORAGE_STACK=minio # seaweedfs と同じストレージ確認
```

`STORAGE_STACK` の既定値は `seaweedfs` です。2つのスタックは同じホストポートを使うため、同時には起動できません。compose の `user-api` / `provider-api` は SeaweedFS 前提の設定なので、このスタックで API を動かす場合はホスト側で起動してください（元々ドキュメントの開発フローもホスト起動です）。MinIO はアーカイブ済みで今後の修正は入らないので、非推奨ドライバのローカル確認以外には使わないでください。

## リリース時の互換性確認

`local:minio` との互換性を確認するため、SeaweedFS を導入するリリース時に以下のテストを実行し、両バックエンドで成功することを確認してください。`local:minio` の削除時期は別途判断します。

```bash
cd backend
make test-storage-compatibility
```

テスト用の SeaweedFS と MinIO を自動で起動・終了し、読み書き・削除・一覧取得・署名付きアップロード／ダウンロードを同じ期待結果で検証します。対象はストレージ操作で、API ワークフロー全体や既存データの移行は含みません。

結果と使用イメージの情報は `backend/storage-compatibility-results/` に保存されます。確認結果は PR に記録してください。

## ストレージ経路の確認

ストレージを差し替えたときや、バージョンを更新したあとの確認用にスクリプトを用意しています。通常の開発では不要です。

`make up` でストレージを起動した状態で、OQTOPUS Cloud が生成する presigned POST を並列実行し、全オブジェクトの内容をストレージから読み戻して確認します。確認後、作成したオブジェクトは自動的に削除されます。

```bash
cd backend
make check-presigned-post PRESIGNED_POST_COUNT=100 PRESIGNED_POST_WORKERS=20
```

対象は presigned URL 生成、HTTP POST、ストレージ実体確認です。ジョブ登録から完了までの API ワークフロー全体は含みません。

同じ経路で POST/GET のスループットとリクエスト遅延も測定できます。最初のラウンドはウォームアップとして集計から除外し、全 GET レスポンスの内容一致も確認します。

```bash
make benchmark-presigned-post \
  PRESIGNED_POST_LABEL=SeaweedFS \
  PRESIGNED_POST_COUNT=5000 \
  PRESIGNED_POST_WORKERS=50 \
  PRESIGNED_POST_PAYLOAD_BYTES=4096 \
  PRESIGNED_POST_ROUNDS=5 \
  PRESIGNED_POST_OUTPUT_JSON=benchmark-results/seaweedfs-4k.json
```

大きいファイルは、例えば `PRESIGNED_POST_COUNT=20`、`PRESIGNED_POST_WORKERS=10`、`PRESIGNED_POST_PAYLOAD_BYTES=104857600`、`PRESIGNED_POST_ROUNDS=3` で実行します。標準出力には ops/s、MiB/s、p50、p95、p99、エラー数の表を表示し、JSON には各ラウンドと実行環境も記録します。GET は各ラウンドで POST した直後のオブジェクトを読むため、コールドリードではなく OQTOPUS Cloud のアップロード・ダウンロード経路に近いワークフロー測定です。

### 測定結果 (2026-08-05 時点)

SeaweedFS と RustFS を同一ホスト・同一条件で測定した結果です。値は転送速度で、全試験を通して HTTP エラー・欠損・内容不一致は 0 件でした。

小さいファイル (4KiB、5,000件・50並列・5ラウンド):

| バックエンド | POST | GET |
| --- | ---: | ---: |
| SeaweedFS | 2.11 MiB/s | 2.61 MiB/s |
| RustFS | 2.18 MiB/s (+3.5%) | 2.63 MiB/s (+0.9%) |

大きいファイル (100MiB、20件・10並列・3ラウンド):

| バックエンド | POST | GET |
| --- | ---: | ---: |
| SeaweedFS | 209 MiB/s (+23%) | 81.5 MiB/s (+9%) |
| RustFS | 169 MiB/s | 75.1 MiB/s |

4KiB ではほぼ同等、100MiB では SeaweedFS が 9〜23% 速いという結果でした。ただし実運用のペイロードは数 KB が中心なので、性能は選定の決め手にしていません。

測定環境は WSL2 上の Docker (14 vCPU / 15GiB RAM、ローカル Docker volume) です。ハードウェアや同居プロセスに強く依存する値なので、絶対値ではなく同条件での相対比較として扱ってください。
