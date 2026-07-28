# Backgrounds Folder

This folder holds the location artwork the bot attaches to episodes. Every
file name below is hardcoded in `data/locations.py` -- replace any of these
placeholder images with your own art using the exact same file name (same
name, `.png` extension) and the bot will pick it up automatically. No code
changes needed.

The placeholders shipped here are plain generated gradient cards with the
location name on them, sized 1024x576 (16:9). Any image works, but matching
that aspect ratio will look best in Discord embeds.

There's also a `default.png` generated alongside the rest. As of 1.1, the
starting location is always either a valid pool key (picked via
`/story-setup`'s autocomplete) or left blank for the AI to choose from this
same pool, so every episode always has a matching image and `default.png`
isn't referenced by any current code path -- it's just there if you want a
fallback image for your own customizations.

## Adding a brand new location

1. Add an entry to the `LOCATIONS` list in `data/locations.py` with a `key`,
   `display_name`, `mood` description, and a `category` (used only to color
   the placeholder generator -- pick any existing category or add a new one
   to `PALETTES` in `scripts/generate_placeholder_backgrounds.py`).
2. Drop an image into this folder named `<key>.png`.
3. That's it -- the new location is now part of the pool the AI can pick
   from, both at story start and at scene changes.

## Full list of expected file names

### Urban / Modern

| File name | Location |
|---|---|
| `abandoned_hospital.png` | Abandoned Hospital |
| `old_lighthouse.png` | Old Lighthouse |
| `subway_station.png` | Late-Night Subway Station |
| `rooftop_garden.png` | Rooftop Garden |
| `downtown_alley.png` | Downtown Alley |
| `grand_library.png` | Grand Library |
| `university_quad.png` | University Quad |
| `corner_coffee_shop.png` | Corner Coffee Shop |
| `high_school_gymnasium.png` | High School Gymnasium |
| `apartment_rooftop.png` | Apartment Rooftop at Dusk |
| `city_park_at_night.png` | City Park at Night |
| `underground_parking_garage.png` | Underground Parking Garage |
| `rundown_motel.png` | Rundown Motel |

### Nature / Wilderness

| File name | Location |
|---|---|
| `enchanted_forest.png` | Enchanted Forest |
| `misty_swamp.png` | Misty Swamp |
| `snowy_mountain_pass.png` | Snowy Mountain Pass |
| `desert_oasis.png` | Desert Oasis |
| `sea_cave.png` | Sea Cave |
| `waterfall_grotto.png` | Waterfall Grotto |
| `ancient_redwood_grove.png` | Ancient Redwood Grove |
| `frozen_tundra.png` | Frozen Tundra |
| `volcanic_crater.png` | Volcanic Crater |
| `coral_reef.png` | Coral Reef |
| `bamboo_forest.png` | Bamboo Forest |
| `autumn_orchard.png` | Autumn Orchard |
| `hidden_valley.png` | Hidden Valley |

### Fantasy / Medieval

| File name | Location |
|---|---|
| `crumbling_castle.png` | Crumbling Castle |
| `wizards_tower.png` | Wizard's Tower |
| `royal_throne_room.png` | Royal Throne Room |
| `village_tavern.png` | Village Tavern |
| `ancient_crypt.png` | Ancient Crypt |
| `dragons_lair.png` | Dragon's Lair |
| `enchanted_library.png` | Enchanted Library |
| `fairy_ring_clearing.png` | Fairy Ring Clearing |
| `mountain_monastery.png` | Mountain Monastery |
| `dwarven_mine.png` | Underground Dwarven Mine |
| `haunted_battlefield.png` | Haunted Battlefield |
| `sacred_grove.png` | Sacred Grove |
| `witchs_cottage.png` | Witch's Cottage |

### Sci-Fi

| File name | Location |
|---|---|
| `derelict_spaceship.png` | Derelict Spaceship |
| `space_station_deck.png` | Space Station Observation Deck |
| `cyberpunk_alley.png` | Cyberpunk Back Alley |
| `terraformed_colony.png` | Terraformed Colony |
| `abandoned_research_lab.png` | Abandoned Research Lab |
| `orbital_elevator.png` | Orbital Elevator Platform |
| `robotics_factory_floor.png` | Robotics Factory Floor |
| `underwater_habitat.png` | Underwater Habitat |
| `alien_marketplace.png` | Alien Marketplace |
| `cargo_bay.png` | Zero-Gravity Cargo Bay |
| `neon_megacity_street.png` | Neon-Lit Megacity Street |
| `cryo_sleep_chamber.png` | Cryo-Sleep Chamber |
| `mining_outpost.png` | Asteroid Mining Outpost |

### Mystery / Horror

| File name | Location |
|---|---|
| `foggy_cemetery.png` | Foggy Cemetery |
| `abandoned_asylum.png` | Abandoned Asylum |
| `locked_study.png` | Locked Study |
| `ships_hold.png` | Creaking Ship's Hold |
| `basement_archive.png` | Basement Archive |
| `old_carnival_grounds.png` | Old Carnival Grounds |
| `isolated_cabin.png` | Isolated Cabin |
| `sealed_vault.png` | Sealed Vault |
| `overgrown_manor.png` | Overgrown Manor |
| `midnight_pier.png` | Midnight Pier |

### Historical / Period

| File name | Location |
|---|---|
| `wild_west_saloon.png` | Wild West Saloon |
| `victorian_parlor.png` | Victorian Parlor |
| `roman_bathhouse.png` | Ancient Roman Bathhouse |
| `egyptian_tomb.png` | Egyptian Tomb |
| `feudal_dojo.png` | Feudal-Era Dojo |
| `renaissance_workshop.png` | Renaissance Workshop |
| `speakeasy_1920s.png` | 1920s Speakeasy |
| `medieval_marketplace.png` | Medieval Marketplace |
| `colonial_harbor.png` | Colonial Harbor |
| `samurai_training_ground.png` | Samurai Training Ground |

### Everyday / Social

| File name | Location |
|---|---|
| `family_kitchen.png` | Family Kitchen |
| `school_rooftop.png` | School Rooftop |
| `office_break_room.png` | Office Break Room |
| `wedding_reception_hall.png` | Wedding Reception Hall |
| `summer_camp_bonfire.png` | Summer Camp Bonfire |
| `late_night_diner.png` | Late-Night Diner |
| `music_studio.png` | Music Studio |
| `art_gallery_opening.png` | Art Gallery Opening |
| `backyard_barbecue.png` | Backyard Barbecue |
| `retirement_home_common_room.png` | Retirement Home Common Room |
| `laundromat_at_midnight.png` | Laundromat at Midnight |
| `rooftop_pool_party.png` | Rooftop Pool Party |
| `small_town_diner_counter.png` | Small-Town Diner Counter |

### Transit / Travel

| File name | Location |
|---|---|
| `airport_terminal_at_night.png` | Airport Terminal at Night |
| `cruise_ship_deck.png` | Cruise Ship Deck |
| `desert_highway_rest_stop.png` | Desert Highway Rest Stop |
| `mountain_cable_car.png` | Mountain Cable Car |
| `river_ferry_crossing.png` | River Ferry Crossing |
| `border_checkpoint.png` | Border Checkpoint |
| `abandoned_train_yard.png` | Abandoned Train Yard |
| `harbor_docks.png` | Harbor Docks |
| `bus_station_lobby.png` | Bus Station Lobby |
| `roadside_diner.png` | Roadside Diner |
| `ferry_terminal_fog.png` | Foggy Ferry Terminal |
| `mountain_trailhead.png` | Mountain Trailhead |
| `small_airfield_hangar.png` | Small Airfield Hangar |
| `night_train_compartment.png` | Night Train Compartment |
| `remote_gas_station.png` | Remote Gas Station at Night |
