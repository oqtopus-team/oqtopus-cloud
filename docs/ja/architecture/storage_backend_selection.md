# ストレージバックエンドの選定

OQTOPUS は大きなジョブペイロードをオブジェクトストレージに保存します (格納形式や API との関係は [量子ジョブの詳細](quantum_jobs_in_detail.md) を参照)。AWS 上ではデフォルトの `s3` ドライバを使いますが、オンプレ環境やローカル開発では自前の S3 互換ストレージを使います。

このページでは、そのバックエンドに SeaweedFS を選んだ経緯と、`seaweedfs` ドライバの設定を説明します。

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

`FSSpecStorage` は SeaweedFS へ AWS S3 と同じ S3 コードパスで接続するので、ストレージ層のコード変更は不要です。認証情報・接続先は `backend/compose.yaml` の `STORAGE_SEAWEEDFS_BUCKET_NAME` / `STORAGE_SEAWEEDFS_USERNAME` / `STORAGE_SEAWEEDFS_PASSWORD` / `STORAGE_SEAWEEDFS_ENDPOINT_URL` で設定します。S3 互換のバックエンドであれば同じコードパスで接続できるため、将来別の実装へ乗り換える場合も変更は接続設定だけで済みます。

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
