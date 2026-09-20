const RPG_ASSETS = {
  heroes: {},
  bosses: {}
};

function loadRpgImages() {
  const heroNames = ["pudge", "juggernaut", "shadow_fiend", "leshrac", "phantom_assassin", "invoker", "wraith_king", "anti_mage"];
  for (const name of heroNames) {
    const img = new Image();
    img.src = `/static/images/heroes/${name}.png`;
    RPG_ASSETS.heroes[name] = img;
  }
  const bossNames = ["faceless_void", "terrorblade", "roshan", "butcher", "shadow_lord"];
  for (const name of bossNames) {
    const img = new Image();
    img.src = `/static/images/bosses/${name}.png`;
    RPG_ASSETS.bosses[name] = img;
  }
}
loadRpgImages();
