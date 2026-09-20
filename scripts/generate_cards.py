import os

suits = {
    'spades': ('♠', '#1a1a2e'),
    'clubs': ('♣', '#1a1a2e'),
    'hearts': ('♥', '#dc2626'),
    'diamonds': ('♦', '#dc2626')
}

ranks = ['2', '3', '4', '5']

out_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'img', 'cards')
os.makedirs(out_dir, exist_ok=True)

for rank in ranks:
    for suit_name, (sym, color) in suits.items():
        svg_path = os.path.join(out_dir, f'{rank}_{suit_name}.svg')
        pips = []
        if rank == '2':
            pips = [(190, 190), (190, 360)]
        elif rank == '3':
            pips = [(190, 160), (190, 275), (190, 390)]
        elif rank == '4':
            pips = [(135, 175), (245, 175), (135, 375), (245, 375)]
        elif rank == '5':
            pips = [(135, 175), (245, 175), (190, 275), (135, 375), (245, 375)]

        pips_xml = ''.join([
            f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="64" font-weight="bold" fill="{color}" text-anchor="middle">{sym}</text>'
            for x, y in pips
        ])

        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 381 531" width="100%" height="100%">
  <rect x="6" y="6" width="369" height="519" rx="24" fill="#ffffff" stroke="#cbd5e1" stroke-width="4"/>
  <!-- Top-Left -->
  <text x="36" y="68" font-family="Arial, sans-serif" font-size="52" font-weight="900" fill="{color}" text-anchor="middle">{rank}</text>
  <text x="36" y="112" font-family="Arial, sans-serif" font-size="42" font-weight="bold" fill="{color}" text-anchor="middle">{sym}</text>

  <!-- Center Pips -->
  {pips_xml}

  <!-- Bottom-Right (inverted) -->
  <g transform="rotate(180 345 463)">
    <text x="345" y="463" font-family="Arial, sans-serif" font-size="52" font-weight="900" fill="{color}" text-anchor="middle">{rank}</text>
    <text x="345" y="507" font-family="Arial, sans-serif" font-size="42" font-weight="bold" fill="{color}" text-anchor="middle">{sym}</text>
  </g>
</svg>'''
        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(svg)

print('Generated 16 card SVGs successfully!')
