from photoalbum.cli import main


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--check-image":
        from image_check import main as check_main
        raise SystemExit(check_main())
    raise SystemExit(main())
