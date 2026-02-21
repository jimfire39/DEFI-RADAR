#!/usr/bin/env python3
"""
Fetches live APY data from DeFiLlama and generates a static HTML dashboard.
Run locally or via GitHub Actions every Monday.
"""

import requests
import json
from datetime import datetime, timezone
from pathlib import Path

# ─── Protocol definitions ────────────────────────────────────────────────────
PROTOCOLS = [
    { "name": "Aave v3",        "icon": "👻", "iconBg": "#b6509e22", "chain": "Ethereum", "category": "Lending",   "risk": "low",    "description": "Leader du lending décentralisé. Déposez USDC/USDT et percevez des intérêts sur la plateforme la plus auditée du marché.",               "strategy": "USDC supply",    "url": "https://app.aave.com",          "accent": "#b6509e", "project": "aave-v3",           "symbol": "USDC",   "search_chain": "Ethereum" },
    { "name": "Morpho",         "icon": "🦋", "iconBg": "#4287f522", "chain": "Ethereum", "category": "Lending",   "risk": "low",    "description": "Protocole peer-to-peer optimisant les taux d'Aave. Meilleurs rendements pour les déposants USDC/USDT.",                             "strategy": "USDC Vault",     "url": "https://morpho.org",            "accent": "#4287f5", "project": "morpho",            "symbol": "USDC",   "search_chain": "Ethereum" },
    { "name": "Lido",           "icon": "🌊", "iconBg": "#00a3ff22", "chain": "Ethereum", "category": "Staking",   "risk": "low",    "description": "Leader du liquid staking ETH. Stakez de l'ETH et recevez du stETH utilisable partout dans l'écosystème DeFi.",                      "strategy": "ETH → stETH",    "url": "https://lido.fi",               "accent": "#00a3ff", "project": "lido",              "symbol": "STETH",  "search_chain": "Ethereum" },
    { "name": "Curve Finance",  "icon": "🔵", "iconBg": "#3a65b622", "chain": "Ethereum", "category": "Liquidity", "risk": "low",    "description": "Référence des pools stablecoins. Frais de swap minimes et rendements solides sur le 3pool et tricrypto.",                           "strategy": "3pool",          "url": "https://curve.fi",              "accent": "#3a65b6", "project": "curve-dex",         "symbol": "3CRV",   "search_chain": "Ethereum" },
    { "name": "Uniswap v3",     "icon": "🦄", "iconBg": "#ff007a22", "chain": "Ethereum", "category": "Liquidity", "risk": "medium", "description": "DEX de référence. Les positions concentrées USDC/ETH 0.05% offrent des rendements élevés pour les LPs actifs.",                  "strategy": "USDC/ETH 0.05%", "url": "https://app.uniswap.org",       "accent": "#ff007a", "project": "uniswap-v3",        "symbol": "USDC",   "search_chain": "Ethereum" },
    { "name": "Pendle Finance", "icon": "📐", "iconBg": "#0dc8c822", "chain": "Ethereum", "category": "Yield",     "risk": "medium", "description": "Tokenisation innovante du yield. PT pour taux fixe garanti, YT pour maximiser le rendement variable sur actifs porteurs d'intérêt.", "strategy": "PT eETH",        "url": "https://www.pendle.finance",    "accent": "#0dc8c8", "project": "pendle",            "symbol": "EETH",   "search_chain": "Ethereum" },
    { "name": "Convex Finance", "icon": "⚡", "iconBg": "#ff6b0022", "chain": "Ethereum", "category": "Yield",     "risk": "medium", "description": "Boost des rendements Curve sans immobiliser de CRV. Maximise les récompenses des pools Curve en empilant les rewards cvxCRV.",    "strategy": "cvxCRV staking", "url": "https://www.convexfinance.com", "accent": "#ff6b00", "project": "convex-finance",    "symbol": "CVXCRV", "search_chain": "Ethereum" },
    { "name": "Ethena",         "icon": "🔷", "iconBg": "#00e5ff22", "chain": "Ethereum", "category": "CDP",       "risk": "medium", "description": "Stablecoin USDe adossé à des positions delta-neutres. Le sUSDe génère du rendement via le funding rate des marchés perpétuels.", "strategy": "sUSDe staking",  "url": "https://www.ethena.fi",         "accent": "#00e5ff", "project": "ethena",            "symbol": "SUSDE",  "search_chain": "Ethereum" },
    { "name": "Kamino",         "icon": "🌀", "iconBg": "#9945ff22", "chain": "Solana",   "category": "Yield",     "risk": "medium", "description": "Yield automatisé sur Solana. Liquidités concentrées sur Orca/Raydium avec rebalancing automatique des fourchettes de prix.",       "strategy": "USDC-SOL vault", "url": "https://kamino.finance",        "accent": "#9945ff", "project": "kamino-liquidity",  "symbol": "USDC",   "search_chain": "Solana" },
    { "name": "Yearn Finance",  "icon": "🏦", "iconBg": "#006ae322", "chain": "Ethereum", "category": "Yield",     "risk": "low",    "description": "Vaults automatisés optimisant en continu les stratégies de rendement. Idéal pour du yield passif sans gestion active.",            "strategy": "yvUSDC vault",   "url": "https://yearn.fi",              "accent": "#006ae3", "project": "yearn-finance",     "symbol": "YVUSDC", "search_chain": "Ethereum" },
]

def fetch_pools():
    print("Fetching pools from DeFiLlama...")
    r = requests.get("https://yields.llama.fi/pools", timeout=30)
    r.raise_for_status()
    pools = r.json()["data"]
    print(f"  → {len(pools)} pools fetched")
    return pools

def find_best_pool(pools, proto):
    candidates = [
        p for p in pools
        if proto["project"].lower() in (p.get("project") or "").lower()
        and (p.get("chain") or "").lower() == proto["search_chain"].lower()
    ]
    sym = proto["symbol"].upper()
    exact = [p for p in candidates if sym in (p.get("symbol") or "").upper()]
    if exact:
        candidates = exact
    candidates.sort(key=lambda p: p.get("tvlUsd") or 0, reverse=True)
    return candidates[0] if candidates else None

def fmt_tvl(v):
    if not v:
        return "—"
    if v >= 1e9:
        return f"${v/1e9:.1f}B"
    if v >= 1e6:
        return f"${v/1e6:.0f}M"
    return f"${v/1e3:.0f}K"

def fmt_apy(v):
    if v is None or (isinstance(v, float) and v != v):  # NaN check
        return "—"
    return f"{v:.1f}%"

def build_html(results, generated_at):
    cards_html = ""
    for i, (proto, pool) in enumerate(results):
        apy     = pool.get("apy")      if pool else None
        tvl     = pool.get("tvlUsd")   if pool else None
        apy_base   = pool.get("apyBase")   if pool else None
        apy_reward = pool.get("apyReward") if pool else None

        apy_display = fmt_apy(apy)
        tvl_display = fmt_tvl(tvl)
        sub_line = ""
        if apy_base and apy_reward and apy_base > 0 and apy_reward > 0:
            sub_line = f'<span class="apy-sub">Base {apy_base:.1f}% + Rewards {apy_reward:.1f}%</span>'

        risk_map = {
            "low":    ("Faible",  "risk-low"),
            "medium": ("Modéré", "risk-medium"),
            "high":   ("Élevé",  "risk-high"),
        }
        risk_label, risk_cls = risk_map.get(proto["risk"], ("—", ""))
        cat_colors = { "Lending":"#4287f5","Liquidity":"#ff007a","Staking":"#00a3ff","CDP":"#00e5ff","Yield":"#7fff6e" }
        cat_color = cat_colors.get(proto["category"], "#aaa")

        delay = i * 60
        cards_html += f"""
        <div class="card" style="--card-accent:{proto['accent']};animation-delay:{delay}ms" data-category="{proto['category']}">
          <div class="card-header">
            <div class="protocol-info">
              <div class="protocol-icon" style="background:{proto['iconBg']}">{proto['icon']}</div>
              <div>
                <div class="protocol-name">{proto['name']}</div>
                <div class="protocol-chain">{proto['chain']}</div>
              </div>
            </div>
            <span class="category-tag" style="color:{cat_color};border-color:{cat_color}44">{proto['category']}</span>
          </div>
          <div class="apy-section">
            <div class="apy-value">{apy_display}</div>
            <div class="apy-meta">
              <span class="apy-label">APY / an</span>
              {sub_line}
            </div>
          </div>
          <div class="risk-tvl">
            <div class="mini-stat">
              <span class="mini-stat-label">Risque</span>
              <span class="mini-stat-value {risk_cls}"><span class="risk-dot"></span>{risk_label}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-stat-label">TVL</span>
              <span class="mini-stat-value">{tvl_display}</span>
            </div>
          </div>
          <p class="description">{proto['description']}</p>
          <div class="card-footer">
            <a href="{proto['url']}" target="_blank" rel="noopener" class="visit-btn">
              Accéder
              <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 8L8 2M5 2h3v3"/></svg>
            </a>
            <span class="strategy-tag">{proto['strategy']}</span>
          </div>
        </div>"""

    # Stats
    apys = [r[1].get("apy") for r in results if r[1] and r[1].get("apy") is not None]
    apys_sorted = sorted(apys)
    max_apy = f"{max(apys):.1f}%" if apys else "—"
    median_apy = f"{apys_sorted[len(apys_sorted)//2]:.1f}%" if apys_sorted else "—"

    date_fr = generated_at.strftime("%-d %B %Y à %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DeFi APY Radar</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet">
<style>
  :root {{ --bg:#080c10;--surface:#0e1520;--border:#1a2535;--accent:#00e5ff;--accent2:#7fff6e;--accent3:#ff6b35;--text:#e2eaf5;--muted:#5a7090;--card-hover:#111d2e; }}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:'Syne',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden;}}
  body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,229,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,229,255,0.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;}}
  .wrapper{{max-width:1100px;margin:0 auto;padding:0 24px;position:relative;z-index:1;}}
  header{{padding:48px 0 32px;border-bottom:1px solid var(--border);}}
  .header-top{{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;}}
  .logo-area h1{{font-size:2.4rem;font-weight:800;letter-spacing:-1px;line-height:1;}}
  .logo-area h1 span{{color:var(--accent);}}
  .logo-area p{{font-family:'Space Mono',monospace;color:var(--muted);font-size:.75rem;margin-top:8px;}}
  .update-badge{{display:flex;flex-direction:column;align-items:flex-end;gap:6px;}}
  .update-label{{font-family:'Space Mono',monospace;font-size:.63rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;}}
  .update-date{{font-family:'Space Mono',monospace;font-size:.78rem;color:var(--accent2);background:rgba(127,255,110,.08);border:1px solid rgba(127,255,110,.2);padding:5px 12px;border-radius:4px;}}
  .update-next{{font-family:'Space Mono',monospace;font-size:.6rem;color:var(--muted);}}
  .stats-bar{{display:flex;gap:32px;margin-top:24px;flex-wrap:wrap;}}
  .stat{{display:flex;flex-direction:column;gap:2px;}}
  .stat-value{{font-size:1.5rem;font-weight:800;color:var(--accent);}}
  .stat-label{{font-family:'Space Mono',monospace;font-size:.63rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;}}
  .filters{{display:flex;gap:8px;margin:28px 0 16px;flex-wrap:wrap;}}
  .filter-btn{{font-family:'Space Mono',monospace;font-size:.68rem;padding:6px 14px;border-radius:4px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;}}
  .filter-btn:hover,.filter-btn.active{{border-color:var(--accent);color:var(--accent);background:rgba(0,229,255,.05);}}
  .disclaimer{{background:rgba(255,107,53,.06);border:1px solid rgba(255,107,53,.2);border-radius:6px;padding:10px 16px;margin-bottom:20px;font-family:'Space Mono',monospace;font-size:.63rem;color:var(--accent3);line-height:1.6;}}
  .protocols-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-bottom:48px;}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:20px;transition:all .2s;position:relative;overflow:hidden;animation:fadeIn .4s ease both;}}
  .card::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--card-accent,var(--accent));opacity:.7;}}
  .card:hover{{background:var(--card-hover);border-color:var(--card-accent,var(--accent));transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,0,0,.4);}}
  @keyframes fadeIn{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:translateY(0)}}}}
  .card-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;}}
  .protocol-info{{display:flex;align-items:center;gap:10px;}}
  .protocol-icon{{width:38px;height:38px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0;}}
  .protocol-name{{font-weight:800;font-size:1rem;}}
  .protocol-chain{{font-family:'Space Mono',monospace;font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-top:2px;}}
  .category-tag{{font-family:'Space Mono',monospace;font-size:.58rem;padding:3px 8px;border-radius:3px;text-transform:uppercase;letter-spacing:.06em;border:1px solid currentColor;opacity:.7;white-space:nowrap;}}
  .apy-section{{display:flex;align-items:flex-end;gap:8px;margin-bottom:14px;}}
  .apy-value{{font-size:2.2rem;font-weight:800;line-height:1;color:var(--card-accent,var(--accent));}}
  .apy-meta{{display:flex;flex-direction:column;gap:2px;margin-bottom:4px;}}
  .apy-label{{font-family:'Space Mono',monospace;font-size:.62rem;color:var(--muted);}}
  .apy-sub{{font-family:'Space Mono',monospace;font-size:.58rem;color:var(--muted);opacity:.8;}}
  .risk-tvl{{display:flex;gap:16px;margin-bottom:14px;}}
  .mini-stat{{display:flex;flex-direction:column;gap:2px;}}
  .mini-stat-label{{font-family:'Space Mono',monospace;font-size:.58rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;}}
  .mini-stat-value{{font-family:'Space Mono',monospace;font-size:.75rem;}}
  .risk-dot{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px;vertical-align:middle;}}
  .risk-low{{color:var(--accent2);}} .risk-low .risk-dot{{background:var(--accent2);}}
  .risk-medium{{color:#ffd166;}} .risk-medium .risk-dot{{background:#ffd166;}}
  .description{{font-size:.77rem;color:var(--muted);line-height:1.5;margin-bottom:16px;}}
  .card-footer{{display:flex;justify-content:space-between;align-items:center;}}
  .visit-btn{{display:inline-flex;align-items:center;gap:6px;font-family:'Space Mono',monospace;font-size:.66rem;padding:7px 14px;border-radius:4px;border:1px solid var(--card-accent,var(--accent));color:var(--card-accent,var(--accent));text-decoration:none;transition:all .15s;}}
  .visit-btn:hover{{background:var(--card-accent,var(--accent));color:var(--bg);}}
  .visit-btn svg{{width:10px;height:10px;}}
  .strategy-tag{{font-family:'Space Mono',monospace;font-size:.58rem;color:var(--muted);background:rgba(255,255,255,.03);padding:3px 7px;border-radius:3px;}}
  footer{{border-top:1px solid var(--border);padding:24px 0;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;}}
  footer p{{font-family:'Space Mono',monospace;font-size:.63rem;color:var(--muted);}}
  footer a{{color:var(--accent);text-decoration:none;}}
</style>
</head>
<body>
<div class="wrapper">
  <header>
    <div class="header-top">
      <div class="logo-area">
        <h1>DEFI <span>YIELD</span> RADAR</h1>
        <p>// MISE À JOUR AUTOMATIQUE CHAQUE LUNDI · DEFILLAMA</p>
      </div>
      <div class="update-badge">
        <span class="update-label">Dernière mise à jour</span>
        <span class="update-date">{date_fr}</span>
        <span class="update-next">↻ Prochaine mise à jour : lundi 8h UTC</span>
      </div>
    </div>
    <div class="stats-bar">
      <div class="stat"><span class="stat-value">{len(results)}</span><span class="stat-label">Protocoles</span></div>
      <div class="stat"><span class="stat-value">{max_apy}</span><span class="stat-label">APY Max</span></div>
      <div class="stat"><span class="stat-value">{median_apy}</span><span class="stat-label">APY Médian</span></div>
    </div>
  </header>

  <div class="filters" id="filters">
    <button class="filter-btn active" data-filter="all">Tous</button>
    <button class="filter-btn" data-filter="Lending">Lending</button>
    <button class="filter-btn" data-filter="Liquidity">Liquidité</button>
    <button class="filter-btn" data-filter="Staking">Staking</button>
    <button class="filter-btn" data-filter="CDP">CDP</button>
    <button class="filter-btn" data-filter="Yield">Yield Agg.</button>
  </div>

  <div class="disclaimer">⚠ APY générés chaque lundi depuis DeFiLlama. Ils varient constamment. Ce dashboard n'est pas un conseil financier — DYOR.</div>

  <div class="protocols-grid" id="grid">
    {cards_html}
  </div>

  <footer>
    <p>Données : <a href="https://defillama.com/yields" target="_blank">DeFiLlama</a> · Généré le {date_fr}</p>
    <p>Automatisé via <a href="https://github.com/features/actions" target="_blank">GitHub Actions</a> · Hébergé sur GitHub Pages</p>
  </footer>
</div>
<script>
  document.getElementById('filters').addEventListener('click', e => {{
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const f = btn.dataset.filter;
    document.querySelectorAll('.card').forEach(c => {{
      c.style.display = (f === 'all' || c.dataset.category === f) ? '' : 'none';
    }});
  }});
</script>
</body>
</html>"""

def main():
    pools = fetch_pools()
    results = []
    for proto in PROTOCOLS:
        pool = find_best_pool(pools, proto)
        name = proto['name']
        if pool:
            print(f"  ✓ {name:20s} → APY {fmt_apy(pool.get('apy')):8s}  TVL {fmt_tvl(pool.get('tvlUsd')):10s}  [{pool.get('symbol','')}]")
        else:
            print(f"  ✗ {name:20s} → not found")
        results.append((proto, pool))

    generated_at = datetime.now(timezone.utc)
    html = build_html(results, generated_at)

    out = Path("docs/index.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"\n✅ Generated → {out}  ({len(html):,} bytes)")

if __name__ == "__main__":
    main()
