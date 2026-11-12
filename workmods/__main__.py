"""Allow ``python -m workmods`` to run the developer CLI."""

from workmods.cli import main

raise SystemExit(main())
