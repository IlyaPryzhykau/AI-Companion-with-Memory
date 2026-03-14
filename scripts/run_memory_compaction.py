"""Manual execution entrypoint for vector-memory deduplication."""

from app.db.session import SessionLocal
from app.services.memory_compaction import _build_arg_parser, compact_vector_memory


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    with SessionLocal() as db:
        try:
            result = compact_vector_memory(
                db,
                user_id=args.user_id,
                near_duplicate_threshold=args.near_threshold,
                dry_run=not args.apply,
            )
            if args.apply:
                db.commit()
            else:
                db.rollback()
        except Exception:
            db.rollback()
            raise

    print(
        "memory_compaction",
        f"dry_run={not args.apply}",
        f"users={result.users_scanned}",
        f"rows={result.rows_scanned}",
        f"deleted={result.rows_deleted}",
        f"exact_deleted={result.exact_duplicates_deleted}",
        f"near_deleted={result.near_duplicates_deleted}",
    )


if __name__ == "__main__":
    main()
