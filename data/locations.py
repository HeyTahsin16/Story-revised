"""
The fixed pool of ~100 locations the AI can choose from for Episode 1 and
for scene changes. Each entry's "key" is exactly the filename (minus .png)
the bot looks for in backgrounds/ -- see backgrounds/README.md.

Deliberately spans several genres (urban, nature, fantasy, sci-fi, mystery,
historical, everyday/social, transit) so this works for a wide range of
owner-chosen themes, not just one genre.
"""
from pathlib import Path

BACKGROUNDS_DIR = Path(__file__).resolve().parent.parent / "backgrounds"

LOCATIONS = [
    # --- Urban / modern ---
    {"key": "abandoned_hospital", "display_name": "Abandoned Hospital", "mood": "sterile halls, flickering lights, forgotten wards", "category": "urban"},
    {"key": "old_lighthouse", "display_name": "Old Lighthouse", "mood": "salt air, creaking stairs, a slow-turning beam", "category": "urban"},
    {"key": "subway_station", "display_name": "Late-Night Subway Station", "mood": "fluorescent hum, distant rumble, an empty platform", "category": "urban"},
    {"key": "rooftop_garden", "display_name": "Rooftop Garden", "mood": "string lights, potted trees, the city skyline below", "category": "urban"},
    {"key": "downtown_alley", "display_name": "Downtown Alley", "mood": "neon reflections in puddles, steam rising from grates", "category": "urban"},
    {"key": "grand_library", "display_name": "Grand Library", "mood": "towering shelves, dust motes in slanted light", "category": "urban"},
    {"key": "university_quad", "display_name": "University Quad", "mood": "old stone buildings, autumn leaves, a distant bell tower", "category": "urban"},
    {"key": "corner_coffee_shop", "display_name": "Corner Coffee Shop", "mood": "espresso steam, low chatter, rain on the window", "category": "urban"},
    {"key": "high_school_gymnasium", "display_name": "High School Gymnasium", "mood": "squeaking sneakers, echoing announcements", "category": "urban"},
    {"key": "apartment_rooftop", "display_name": "Apartment Rooftop at Dusk", "mood": "laundry lines, distant sirens, warm fading light", "category": "urban"},
    {"key": "city_park_at_night", "display_name": "City Park at Night", "mood": "empty swings, a single streetlamp's glow", "category": "urban"},
    {"key": "underground_parking_garage", "display_name": "Underground Parking Garage", "mood": "dripping pipes, flickering fluorescents", "category": "urban"},
    {"key": "rundown_motel", "display_name": "Rundown Motel", "mood": "buzzing neon sign, thin walls, the distant highway", "category": "urban"},

    # --- Nature / wilderness ---
    {"key": "enchanted_forest", "display_name": "Enchanted Forest", "mood": "glowing moss, unnatural quiet, watching shadows", "category": "nature"},
    {"key": "misty_swamp", "display_name": "Misty Swamp", "mood": "waist-deep fog, croaking frogs, half-sunk ruins", "category": "nature"},
    {"key": "snowy_mountain_pass", "display_name": "Snowy Mountain Pass", "mood": "biting wind, thin air, a distant rumble of snow", "category": "nature"},
    {"key": "desert_oasis", "display_name": "Desert Oasis", "mood": "palm shade, cracked earth, mirages on the horizon", "category": "nature"},
    {"key": "sea_cave", "display_name": "Sea Cave", "mood": "echoing waves, bioluminescent pools, tide-worn passages", "category": "nature"},
    {"key": "waterfall_grotto", "display_name": "Waterfall Grotto", "mood": "roaring water, cool mist, a hidden ledge behind the falls", "category": "nature"},
    {"key": "ancient_redwood_grove", "display_name": "Ancient Redwood Grove", "mood": "towering trunks, filtered green light", "category": "nature"},
    {"key": "frozen_tundra", "display_name": "Frozen Tundra", "mood": "endless white, cracking ice, aurora overhead", "category": "nature"},
    {"key": "volcanic_crater", "display_name": "Volcanic Crater", "mood": "sulfur haze, glowing fissures, trembling ground", "category": "nature"},
    {"key": "coral_reef", "display_name": "Coral Reef", "mood": "shifting light through water, darting fish, coral spires", "category": "nature"},
    {"key": "bamboo_forest", "display_name": "Bamboo Forest", "mood": "creaking stalks, dappled light, a constant wind-song", "category": "nature"},
    {"key": "autumn_orchard", "display_name": "Autumn Orchard", "mood": "fallen apples, crisp air, distant crows", "category": "nature"},
    {"key": "hidden_valley", "display_name": "Hidden Valley", "mood": "sheer cliffs, wildflowers, a river running through", "category": "nature"},

    # --- Fantasy / medieval ---
    {"key": "crumbling_castle", "display_name": "Crumbling Castle", "mood": "ivy-choked towers, echoing halls, a cold throne", "category": "fantasy"},
    {"key": "wizards_tower", "display_name": "Wizard's Tower", "mood": "floating candles, humming sigils, a narrow spiral stair", "category": "fantasy"},
    {"key": "royal_throne_room", "display_name": "Royal Throne Room", "mood": "banners, tension, a watching court", "category": "fantasy"},
    {"key": "village_tavern", "display_name": "Village Tavern", "mood": "firelight, ale-soaked floorboards, hushed rumors", "category": "fantasy"},
    {"key": "ancient_crypt", "display_name": "Ancient Crypt", "mood": "cold stone, faded carvings, an unsettling silence", "category": "fantasy"},
    {"key": "dragons_lair", "display_name": "Dragon's Lair", "mood": "scorched stone, a glittering hoard, slow breathing in the dark", "category": "fantasy"},
    {"key": "enchanted_library", "display_name": "Enchanted Library", "mood": "whispering books, drifting motes of light", "category": "fantasy"},
    {"key": "fairy_ring_clearing", "display_name": "Fairy Ring Clearing", "mood": "a mushroom circle, unnatural stillness", "category": "fantasy"},
    {"key": "mountain_monastery", "display_name": "Mountain Monastery", "mood": "chanting echoes, incense, thin mountain air", "category": "fantasy"},
    {"key": "dwarven_mine", "display_name": "Underground Dwarven Mine", "mood": "pickaxe echoes, glittering veins, deep tunnels", "category": "fantasy"},
    {"key": "haunted_battlefield", "display_name": "Haunted Battlefield", "mood": "rusted blades, drifting mist, old grief in the air", "category": "fantasy"},
    {"key": "sacred_grove", "display_name": "Sacred Grove", "mood": "ancient standing stones, hushed reverence", "category": "fantasy"},
    {"key": "witchs_cottage", "display_name": "Witch's Cottage", "mood": "hanging herbs, a crackling hearth, a watchful cat", "category": "fantasy"},

    # --- Sci-fi ---
    {"key": "derelict_spaceship", "display_name": "Derelict Spaceship", "mood": "dead consoles, drifting debris, emergency lights", "category": "scifi"},
    {"key": "space_station_deck", "display_name": "Space Station Observation Deck", "mood": "a starfield view, the quiet hum of systems", "category": "scifi"},
    {"key": "cyberpunk_alley", "display_name": "Cyberpunk Back Alley", "mood": "neon signage, rain-slick pavement, distant drone hum", "category": "scifi"},
    {"key": "terraformed_colony", "display_name": "Terraformed Colony", "mood": "a domed sky, engineered fields, distant machinery", "category": "scifi"},
    {"key": "abandoned_research_lab", "display_name": "Abandoned Research Lab", "mood": "shattered glass, dead monitors, warning tape", "category": "scifi"},
    {"key": "orbital_elevator", "display_name": "Orbital Elevator Platform", "mood": "vertigo-inducing height, the cable creaking upward", "category": "scifi"},
    {"key": "robotics_factory_floor", "display_name": "Robotics Factory Floor", "mood": "clanking arms, sparks, conveyor hum", "category": "scifi"},
    {"key": "underwater_habitat", "display_name": "Underwater Habitat", "mood": "a groaning hull, blue light, distant sonar pings", "category": "scifi"},
    {"key": "alien_marketplace", "display_name": "Alien Marketplace", "mood": "strange smells, unfamiliar tongues, bartering crowds", "category": "scifi"},
    {"key": "cargo_bay", "display_name": "Zero-Gravity Cargo Bay", "mood": "floating crates, tethered footing, hissing airlocks", "category": "scifi"},
    {"key": "neon_megacity_street", "display_name": "Neon-Lit Megacity Street", "mood": "holograms, crowd noise, warm rain", "category": "scifi"},
    {"key": "cryo_sleep_chamber", "display_name": "Cryo-Sleep Chamber", "mood": "frost-rimmed glass, slow beeping, held breath", "category": "scifi"},
    {"key": "mining_outpost", "display_name": "Asteroid Mining Outpost", "mood": "low gravity, fine dust, distant drilling", "category": "scifi"},

    # --- Mystery / horror ---
    {"key": "foggy_cemetery", "display_name": "Foggy Cemetery", "mood": "leaning headstones, distant crow calls", "category": "mystery"},
    {"key": "abandoned_asylum", "display_name": "Abandoned Asylum", "mood": "peeling paint, echoing corridors, old restraints", "category": "mystery"},
    {"key": "locked_study", "display_name": "Locked Study", "mood": "a ticking clock, locked drawers, a half-burned letter", "category": "mystery"},
    {"key": "ships_hold", "display_name": "Creaking Ship's Hold", "mood": "swaying lanterns, stacked crates, water lapping below", "category": "mystery"},
    {"key": "basement_archive", "display_name": "Basement Archive", "mood": "a flickering bulb, endless file boxes, dust", "category": "mystery"},
    {"key": "old_carnival_grounds", "display_name": "Old Carnival Grounds", "mood": "rusted rides, a faded music-box tune", "category": "mystery"},
    {"key": "isolated_cabin", "display_name": "Isolated Cabin", "mood": "howling wind, one lit window, deep snow", "category": "mystery"},
    {"key": "sealed_vault", "display_name": "Sealed Vault", "mood": "a thick door, humming locks, held-breath silence", "category": "mystery"},
    {"key": "overgrown_manor", "display_name": "Overgrown Manor", "mood": "broken shutters, ivy, a portrait that seems to watch", "category": "mystery"},
    {"key": "midnight_pier", "display_name": "Midnight Pier", "mood": "creaking wood, black water, a single swinging lantern", "category": "mystery"},

    # --- Historical / period ---
    {"key": "wild_west_saloon", "display_name": "Wild West Saloon", "mood": "swinging doors, piano, dust and whiskey", "category": "historical"},
    {"key": "victorian_parlor", "display_name": "Victorian Parlor", "mood": "heavy drapes, a ticking mantel clock, hushed propriety", "category": "historical"},
    {"key": "roman_bathhouse", "display_name": "Ancient Roman Bathhouse", "mood": "steam, marble, echoing voices", "category": "historical"},
    {"key": "egyptian_tomb", "display_name": "Egyptian Tomb", "mood": "torchlight, hieroglyphs, stale ancient air", "category": "historical"},
    {"key": "feudal_dojo", "display_name": "Feudal-Era Dojo", "mood": "polished floors, incense, disciplined silence", "category": "historical"},
    {"key": "renaissance_workshop", "display_name": "Renaissance Workshop", "mood": "paint fumes, half-finished canvases, candlelight", "category": "historical"},
    {"key": "speakeasy_1920s", "display_name": "1920s Speakeasy", "mood": "jazz, cigarette smoke, a hidden door", "category": "historical"},
    {"key": "medieval_marketplace", "display_name": "Medieval Marketplace", "mood": "hawking vendors, mud streets, distant church bells", "category": "historical"},
    {"key": "colonial_harbor", "display_name": "Colonial Harbor", "mood": "creaking ships, salt air, dockside bustle", "category": "historical"},
    {"key": "samurai_training_ground", "display_name": "Samurai Training Ground", "mood": "clacking bokken, raked gravel, discipline", "category": "historical"},

    # --- Everyday / social ---
    {"key": "family_kitchen", "display_name": "Family Kitchen", "mood": "a simmering pot, a worn table, familiar warmth", "category": "everyday"},
    {"key": "school_rooftop", "display_name": "School Rooftop", "mood": "wind, a distant bell, a quiet place to talk", "category": "everyday"},
    {"key": "office_break_room", "display_name": "Office Break Room", "mood": "a humming fridge, bad coffee, fluorescent light", "category": "everyday"},
    {"key": "wedding_reception_hall", "display_name": "Wedding Reception Hall", "mood": "string lights, clinking glasses, music", "category": "everyday"},
    {"key": "summer_camp_bonfire", "display_name": "Summer Camp Bonfire", "mood": "crackling flames, marshmallow smoke, a wide night sky", "category": "everyday"},
    {"key": "late_night_diner", "display_name": "Late-Night Diner", "mood": "a neon sign, a tired waitress, bottomless coffee", "category": "everyday"},
    {"key": "music_studio", "display_name": "Music Studio", "mood": "soundproof foam, humming amps, half-written lyrics", "category": "everyday"},
    {"key": "art_gallery_opening", "display_name": "Art Gallery Opening", "mood": "hushed conversation, wine, careful footsteps", "category": "everyday"},
    {"key": "backyard_barbecue", "display_name": "Backyard Barbecue", "mood": "smoke, laughter, string lights at dusk", "category": "everyday"},
    {"key": "retirement_home_common_room", "display_name": "Retirement Home Common Room", "mood": "soft chatter, old photographs, tea", "category": "everyday"},
    {"key": "laundromat_at_midnight", "display_name": "Laundromat at Midnight", "mood": "spinning drums, the hum of machines", "category": "everyday"},
    {"key": "rooftop_pool_party", "display_name": "Rooftop Pool Party", "mood": "splashing water, music, city lights", "category": "everyday"},
    {"key": "small_town_diner_counter", "display_name": "Small-Town Diner Counter", "mood": "regulars, gossip, the smell of pancakes", "category": "everyday"},

    # --- Transit / travel ---
    {"key": "airport_terminal_at_night", "display_name": "Airport Terminal at Night", "mood": "empty gates, muted announcements", "category": "transit"},
    {"key": "cruise_ship_deck", "display_name": "Cruise Ship Deck", "mood": "ocean spray, band music, string lights", "category": "transit"},
    {"key": "desert_highway_rest_stop", "display_name": "Desert Highway Rest Stop", "mood": "heat shimmer, a buzzing vending machine", "category": "transit"},
    {"key": "mountain_cable_car", "display_name": "Mountain Cable Car", "mood": "a swaying cabin, a vertigo view, creaking cables", "category": "transit"},
    {"key": "river_ferry_crossing", "display_name": "River Ferry Crossing", "mood": "engine thrum, lapping water, a fading shoreline", "category": "transit"},
    {"key": "border_checkpoint", "display_name": "Border Checkpoint", "mood": "idling engines, tense quiet, floodlights", "category": "transit"},
    {"key": "abandoned_train_yard", "display_name": "Abandoned Train Yard", "mood": "rusted cars, overgrown tracks", "category": "transit"},
    {"key": "harbor_docks", "display_name": "Harbor Docks", "mood": "creaking ropes, gull cries, diesel and salt", "category": "transit"},
    {"key": "bus_station_lobby", "display_name": "Bus Station Lobby", "mood": "hard benches, echoing announcements", "category": "transit"},
    {"key": "roadside_diner", "display_name": "Roadside Diner", "mood": "a neon sign, truckers, endless highway outside", "category": "transit"},
    {"key": "ferry_terminal_fog", "display_name": "Foggy Ferry Terminal", "mood": "a foghorn, dim lights, distant waves", "category": "transit"},
    {"key": "mountain_trailhead", "display_name": "Mountain Trailhead", "mood": "cool morning air, distant birdsong", "category": "transit"},
    {"key": "small_airfield_hangar", "display_name": "Small Airfield Hangar", "mood": "oil and metal smell, a slow propeller creak", "category": "transit"},
    {"key": "night_train_compartment", "display_name": "Night Train Compartment", "mood": "rhythmic clatter, passing lights", "category": "transit"},
    {"key": "remote_gas_station", "display_name": "Remote Gas Station at Night", "mood": "a buzzing sign, empty pumps, moths in the light", "category": "transit"},
]

LOCATIONS_BY_KEY = {loc["key"]: loc for loc in LOCATIONS}


def search_locations(query: str, limit: int = 25) -> list:
    """
    Simple, dependency-free search across the location pool by display
    name, key, and category. This is what powers /story-setup's
    starting_location autocomplete.

    Discord's static per-option "choices=[]" list is hard-capped at 25
    entries -- nowhere near enough for a 100+ location pool. Autocomplete
    is the actual, Discord-native way past that: instead of pre-registering
    a fixed list, the bot re-runs a search like this one on every keystroke
    and returns up to 25 *matching* suggestions. The displayed suggestion
    count is still capped at 25 (that part of the limit is a hard Discord
    API constraint on any single autocomplete response), but the pool being
    searched is not capped at all -- add a 500th location and it's
    immediately searchable, no code changes needed.
    """
    query = (query or "").strip().lower()
    if not query:
        return LOCATIONS[:limit]

    scored = []
    for loc in LOCATIONS:
        haystacks = (loc["display_name"].lower(), loc["key"].replace("_", " "), loc["category"])
        if any(query in h for h in haystacks):
            starts_with = loc["display_name"].lower().startswith(query)
            scored.append((0 if starts_with else 1, loc["display_name"], loc))

    scored.sort(key=lambda triple: (triple[0], triple[1]))
    return [loc for _, _, loc in scored[:limit]]
