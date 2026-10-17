# Source acceptance and immutable checkpoint amendment — protocol v2.2

Owner authorization: complete the missing minimal source-acceptance/freeze recording procedure and execute it for the existing verified cohort, conditional on all checks passing. This is an operational amendment to base protocol2.1, whose SHA256 is af30cd1e76d566dcc449d6f634b4b85077a766f7bacdb599737fd169107b2d23. It does not change that file, intake2.1.0, profile2.0, scientific definitions, selected dates, raw bytes or candles.

## Prerequisites and decision

The existing candidate verifier must pass, including original raw/derived hashes, identities, all ten frozen dates, Chicago calendar, complete sessions, exact first250 windows, OHLCV, one-minute continuity, Decimal aggregation and provenance metadata. Require the expected candidate manifest and raw SHA256 supplied by the owner. Every window uses cohort mnq-202609-5m-v2, profile NT_LOCAL_HISTORY_MINUTE_LAST_UTC_V2 and aggregation2.1.0. Provider/upstream_origin_status stay UNVERIFIED. The owner-attested original local export, no external imports and unedited TXT are preserved; neither supplier authenticity nor historical adjustment history is independently proven. The four existing legacy candle comparisons are retained and reviewed. For this batch they must remain exact MATCH.

One independent scoped review covers implementation/amendment and actual source-candidate provenance/quality prerequisites. Its ordinary evidence record must contain review_kind=SOURCE_FREEZE_SCOPED_REVIEW_V1, decision=APPROVED_FOR_SOURCE_ACCEPTANCE_AND_FREEZE, empty critical_findings/important_findings, candidate_manifest_sha256, implementation_sha256, protocol_amendment_sha256 and successor_recognition_or_oracle_occurred=false. This is the requested review evidence, not a signing system, ROOT authority, service or new operator permission. It must bind the exact code, amendment and candidate; unresolved findings or wrong bindings are HOLD. The stage declaration is based on owner attestation and scoped package/task records; it is not proof about unobserved execution elsewhere.

Under the owner's existing conditional acceptance authorization, successful final validation records acceptance_decision=ACCEPTED, actual UTC accepted_at_utc and acceptance_basis. No further owner approval is needed for routine execution in this task. Never infer acceptance from software tests alone.

## Authoritative checkpoint

Authoritative accepted dataset identity: mnq-202609-5m-v2. Official destination: validation/mnq_5m_successor_v2/frozen/mnq-202609-5m-v2 in the authoritative worktree. Synthetic tests use isolated temporary directories and are not official checkpoints.

There is one immutable-by-procedure directory: original candidate files under candidate/, preserved intake/freeze programs and base/amended protocols under support/, and the scoped review under evidence/. Original candidate manifest remains VALIDATED_CANDIDATE_NOT_ACCEPTED/source_cohort_frozen=false as historical evidence; acceptance is recorded only by the enclosing freeze-manifest.json.

The single machine-readable freeze-manifest.json binds cohort identity, all ten ordered date/path/window hashes and first/last closes, expected candidate/raw hashes, config/profile/calendar hashes, aggregation version, frozen science commit, explicit UNVERIFIED origin and limitations, acceptance decision/time/basis, and every snapshot file's relative path, byte length and SHA256. Cohort+ordered case path/date identifies each window. Its schema is MNQ_SOURCE_COHORT_FREEZE_V1. The artifact list excludes the freeze manifest itself. Its SHA256 is emitted only after complete verification and recorded outside the snapshot in the continuation handoff; no circular or self-referential hash exists.

## Publication, incomplete writes and verification

Use the existing verified candidate, never rebuild or modify its candles. Prevalidate and capture its exact bytes, require a new destination outside the source candidate, use exclusive file creation and fsync file contents, and read back every snapshot artifact. Re-run candidate verification within the preserved snapshot. Write freeze-manifest.json LAST as the completion marker, then verify its externally expected SHA, every artifact, exact membership and all cohort bindings before reporting success.

Any mismatch or I/O error is HOLD. Never accept a partial directory or overwrite/reuse an existing checkpoint, even if incomplete. Preserve incomplete output for diagnosis; there is no automatic delete, repair or retry. A missing/truncated manifest or missing/modified/extra file fails verification. File fsync does not guarantee survival of every OS/storage failure; future verification must detect loss or corruption. Hashes do not prevent writing and are not signatures. Immutability here means no in-place changes through the procedure plus externally pinned hashes for tamper detection. Do not modify attributes/ACLs and claim they establish physical immutability.

Future verification uses the preserved program in isolated Python mode, from any working directory, with the expected freeze-manifest SHA from the external handoff:

    D:\python\python.exe -I -B <snapshot>\support\mnq_5m_source_freeze_v2.py verify --snapshot <snapshot> --expected-manifest-sha256 <external_SHA256>

Preserved intake re-parses the original raw minutes and re-derives all ten outputs; no NinjaTrader or repository imports are required. The freeze manifest records Python and tzdata versions (or explicitly reports system timezone data without a package version). Use that recorded environment. Nothing in this operation invokes production recognition or independent oracles, modifies legacy sources or changes the current scientific stage. After freeze, complete the deferred Chapter2 market-state/SMS/BMS scope audit before independent oracle freezing; all-source → all-oracle → blind-production → comparison ordering remains.
