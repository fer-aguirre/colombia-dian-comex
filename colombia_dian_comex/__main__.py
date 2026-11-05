"""Permite correr la CLI de consulta con `python -m colombia_dian_comex`.

Alternativa al comando `colombia-dian-query`, útil cuando Windows bloquea el
ejecutable que genera uv.
"""

from colombia_dian_comex.query import main

raise SystemExit(main())
