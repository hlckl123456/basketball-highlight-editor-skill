# 视频来源与许可

全部十段视频允许按所列许可再分发。原片引用已在仓库的相对路径中固定；四段新原片位于 `sources/`，其余复用既有案例文件。

本目录 `review-media/` 是 H264/AAC 本地播放副本，保留画幅比例，缩小到不超过 960×720；其视频、帧和相关派生媒体继续使用来源许可。程序源码的 MIT 不替代媒体许可。

| ID / split | 作者 | 许可与原页面 | 下载日期 | 场景 |
| --- | --- | --- | --- | --- |
| indiana / development | Koavf / Justin Anthony Knapp | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) · [来源](https://commons.wikimedia.org/wiki/File:Indiana_Legends_Versus_Indiana_Lyons,_20240224_183141_(165)_(165).webm) | 2026-10-27 | indoor_competition |
| university / development | Alejons06 | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) · [来源](https://commons.wikimedia.org/wiki/File:Cancha_de_basquetbol_universidad.webm) | 2026-10-27 | outdoor_university |
| moscow1 / development | Predatorsamsung | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0) · [来源](https://commons.wikimedia.org/wiki/File:Streetball_in_Moscow_Bolshoy_Spasoglinishchevsky_lane.webm) | 2026-10-27 | outdoor_community |
| moscow2 / development | Predatorsamsung | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0) · [来源](https://commons.wikimedia.org/wiki/File:Streetball_in_Moscow_Bolshoy_Spasoglinishchevsky_lane2.webm) | 2026-10-27 | outdoor_community |
| ljubljana / development | Detlef Stöcker | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0) · [来源](https://commons.wikimedia.org/wiki/File:Sportpark_Ljubljana_-_Skateboard_and_Basketball_Aerials_by_Yuneec_Typhoon_Q500_4k.webm) | 2026-10-27 | outdoor_park |
| ukraine / development | Viktor O. Ledenyov | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) · [来源](https://commons.wikimedia.org/wiki/File:(2)_BASKETBALL_GAME_IN_TOWN_OF_BAR_REGION_OF_VINNYTSIA_STATE_OF_UKRAINE_VIDEO_BY_VIKTOR_O_LEDENYOV_20160507.ogv) | 2026-10-27 | outdoor_community |
| zhijiang / development | Ambassador of the United States of America to the People's Republic of China | [Public domain](https://commons.wikimedia.org/wiki/File:Ambassador_Nicholas_Burns_plays_basketball_with_Chinese_students_in_Zhijiang_Dong_Autonomous_County.webm) · [来源](https://commons.wikimedia.org/wiki/File:Ambassador_Nicholas_Burns_plays_basketball_with_Chinese_students_in_Zhijiang_Dong_Autonomous_County.webm) | 2026-10-28 | outdoor_school |
| dribbling / holdout | Mart570 | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) · [来源](https://commons.wikimedia.org/wiki/File:Basketball-Basic_Types_of_Dribbling.webm) | 2026-10-28 | indoor_practice |
| skills-basic / holdout | Azorbli | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) · [来源](https://commons.wikimedia.org/wiki/File:Basketball_(1).ogv) | 2026-10-28 | outdoor_community |
| nabua / holdout | Yawrei | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) · [来源](https://commons.wikimedia.org/wiki/File:Nabua_street_basketball_WTR.webm) | 2026-10-28 | outdoor_roadside |

逐文件 SHA256、字节数、时长、拍摄条件和源路径见 [catalog.json](catalog.json)。四段新视频的 Commons API 原始许可记录见 [download-receipts.json](download-receipts.json)。来源中的球员不是任务用户，原作者不为本项目背书。

乌克兰原视频在既有案例中旋转了 90 度并去掉音轨，本目录沿用该副本，继续遵循 CC BY-SA 4.0。Ljubljana 仅将 129 到 189 秒设为篮球评测区间，原片仍完整保留。

`zhijiang` 来源为美国驻华大使官方账户发布的履职活动短片，Commons 标为 Public domain；保留来源页和原始元数据作为依据。它是约 6 秒的学校球场公众活动片段，不作为完整业余比赛代表。

`dribbling` 是室内运球示范，`skills-basic` 是土场练习，均非完整比赛。作为困难条件或非进球对照保留，不能把片段数当作独立完整比赛数。莫斯科两段来自同一事件，已放入同一个 development 拍摄组。

许可证据不足或不能再分发的素材将放到被忽略的 `eval/local-media/`，只提交来源、许可、下载脚本和哈希；本轮没有采用此类素材。
