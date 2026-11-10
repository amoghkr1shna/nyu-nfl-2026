# Breaking Ankles: Why Sharp Cuts Don’t Beat Man Coverage

Coaches call sharp-breaking routes "man beaters." I measured the cut on **31,601 routes** from 2021 Next Gen Stats tracking data and found that sharp cuts gain **no extra space against man coverage**. Instead, man defenders take away about **0.3 yards more on every cut, sharp or soft**, so a receiver needs something other than a hard cut to win against man.

**Interactive version:** [explore the findings](https://amoghkr1shna.github.io/nyu-nfl-2026/), with a position toggle, player search and sortable leaderboard.

![Sharp cuts don't beat man coverage](outputs/figures/sharpness_vs_separation.png)

*How to read it:* each point is the average space a receiver gains on his defender during the cut, for one range of cut angles. The red (man) line sits below the blue (zone) line in 11 of 12 points, and sharper cuts never close the gap.

*Running backs are shown for completeness but are the least reliable panel. Their sharpest "break" is often the turn out of the backfield rather than a cut against a defender. The headline rests on wide receivers and tight ends.*

## Results 

Fair comparison of similar cuts (same starting gap, same timing, same route depth, same time to throw):

| | Wide receivers | Tight ends | Running backs |
|---|---|---|---|
| Routes | 18,965 | 7,270 | 5,366 |
| **Space lost vs man, per cut** | **−0.31 yd** | **−0.24 yd** | −0.19 yd |
| Do sharper cuts help *more* vs man? | No (−0.02, not significant) | No (−0.02, n.s.) | No (−0.04, n.s.) |
| Keeping speed through the cut | Helps slightly (+0.05 yd) | Helps slightly (+0.07 yd) | Hurts (−0.11 yd) |

If sharp cuts really beat man coverage, that second row would show a clear positive number. For every position, it’s flat.

## Who's the shiftiest, and does it pay off?

![Being shifty doesn't decide who wins against man](outputs/figures/shiftiness_vs_man.png)

Shiftiness (a player's average Break Sharpness) barely predicts who wins against man: rank correlation **+0.10** across 112 wide receivers. **4 of the 5 shiftiest WRs gain less space against man than the median receiver**, and the best receiver against man, Dyami Brown, is only mid-pack on shiftiness.

The full leaderboard for every position is sortable and searchable in the [interactive version](https://amoghkr1shna.github.io/nyu-nfl-2026/) (also in [`outputs/leaderboard.csv`](outputs/leaderboard.csv)).

## Same kind of cut, different result

![Same kind of cut, different result](outputs/figures/top_plays.png)

Two real plays with similar cuts. **Against man (Cover-1)**, Chris Godwin's 49° cut doesn't shake his defender, who closes from 2.2 to 1.1 yards, and the pass falls incomplete. **Against zone (Cover-3)**, DeVonta Smith's 58° cut opens the gap from 1.1 to 2.8 yards, and he catches a 21-yard pass.

## Player callout: Cooper Kupp

Kupp (2021 Triple Crown season) ranks only **72nd of 112 WRs in shiftiness** and is exactly average against man (56th). Against zone he's **5th best** (+0.22 yd per cut), and his man-vs-zone gap is the 10th largest of the 112. **Kupp doesn't win by cutting; he wins by finding space against zone.**

## What coaches and scouts can do with this

- **Coaches:** don't pick your "man beaters" by how sharply a receiver cuts. Against man-heavy defenses, sharp cuts alone don't buy extra space, so the space has to come from somewhere else.
- **Scouts:** shiftiness is a style, not a predictor of winning against man. Grade man and zone separately: a receiver like Kupp can be average against man and elite against zone.

## How I measured it

**1. Break Sharpness (the stat).** For each route between the snap and the throw, I found the receiver's largest change of direction over 0.5 s (5 frames at 10 fps) and multiply it by how much speed he kept (speed after ÷ speed before, capped at 1).
- Before measuring, every play is flipped so the offense moves the same way.
- Direction is *unwrapped* so a heading going from 359° to 1° counts as a 2° turn, instead of 358°.

**2. Space gained (the outcome).** When the cut starts, I found the nearest coverage defender and measure the gap to **that same defender** again 0.5 s later, when the cut ends. Following one defender isolates what the cut did to the man on him.

**3. Fair comparison.** Sharper cuts tend to happen later in the route and start with the defender closer, and both change how much space opens up regardless of the cut. Without adjusting, sharp cuts look like they create space; once I compared similar situations, that effect disappears. I adjusted for **starting gap, cut timing, route depth and time to throw**, using a regression with robust standard errors ([`outputs/regression_summary.csv`](outputs/regression_summary.csv)).

**Sample:** 122 games, 7,105 pass plays labeled man or zone by PFF (sacks, scrambles and "Other" coverages removed), 31,601 WR/TE/RB routes (9,435 vs man, 22,166 vs zone).

## How to run

All results are already in `outputs/`. To rebuild them from the raw data (about a minute), see [REPRODUCE.md](REPRODUCE.md).