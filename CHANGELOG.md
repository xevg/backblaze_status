# CHANGELOG



## 0.12.9 (2024-05-15)

### Fix

- **ToDoFiles**: change how to detect skipped files
- **Signals**: add update_chunk
- **QtMainWindow**: change font
- **QtBackupStatus**: add transmitted chunk
- **BzTransmit**: reverse read previous file to get current filename
- **BzPrepare**: take out debug statement
- **BzLastFileTransmitted**: take out debug statement
- **BzDataTableModel**: add error checking and column spaces
- **ToDoFiles**: add commas

### Refactor

- **ChunkModel**: change management of chunk display

## 0.12.8 (2024-05-09)

### Refactor

- update metadata

## 0.12.7 (2024-05-09)

### Fix

- **ChunkDialog**: add resize option
- **workers**: add comments and cleanup
- **workers**: add comments and cleanup
- **Utils**: add comments and cleanup
- **ToDoFiles**: add comments and cleanup
- **QtBackupStatus**: fix dialog box
- **CurrentState**: Add flag for ToDo file read
- **BzTransmit**: change how to get current file so I get it earlier
- **BzDataTableModel**: add commas to field

### Refactor

- remove unnecessary files

## 0.12.6 (2024-05-08)

### Refactor

- **ToDoDialogModel**: add comments and clean up

## 0.12.5 (2024-05-08)

### Refactor

- **ToDoDialog**: add comments and clean up

## 0.12.4 (2024-05-08)

### Refactor

- remove unnecessary files
- **Signals**: add comments and clean up

## 0.12.3 (2024-05-08)

### Refactor

- **QtMainWindow**: add comments and minor fixes

## 0.12.2 (2024-05-08)

### Refactor

- **QtBackupStatus**: add comments and minor fixes

## 0.12.1 (2024-05-08)

### Refactor

- **locks**: removed unnecessary files

## 0.12.0 (2024-05-08)

### Feat

- **exceptions**: add comment

## 0.11.0 (2024-05-08)

### Feat

- **CurrentState**: add locking

### Refactor

- add comments to constants.py

## 0.10.9 (2024-05-08)

### Refactor

- comments and cleanup
- comments and cleanup and minor fixes
- comments and cleanup

## 0.10.8 (2024-05-08)

### Refactor

- optimize imports
- add comments and clean up

## 0.10.7 (2024-05-08)

### Refactor

- add comments and clean up
- optimize imports

## 0.10.6 (2024-05-08)

### Refactor

- file no longer used

## 0.10.5 (2024-05-08)

### Refactor

- comments and cleanup

## 0.10.4 (2024-05-08)

### Fix

- add comments, add go_to_top and fix fetchLess to move up

### Refactor

- comments
- updated

## 0.10.3 (2024-05-08)

### Refactor

- remove unnecessary files

## 0.10.2 (2024-05-08)

### Refactor

- update for CurrentState

## 0.10.1 (2024-05-08)

### Fix

- many changes and cleanup

### Refactor

- cleanup
- Create status_table
- make class for chunk dialog
- clean up

## 0.10.0 (2024-05-08)

### Feat

- many changes

### Fix

- add skipped, remaining, and stats

### Refactor

- Add constants

## 0.9.5 (2024-05-08)

### Fix

- add QTableWidget

### Refactor

- use CurrentState

## 0.9.4 (2024-05-08)

### Fix

- added debugging

## 0.9.3 (2024-05-08)

### Refactor

- refactored

## 0.9.2 (2024-05-08)

### Fix

- add current state

## 0.9.1 (2024-05-08)

### Fix

- remove unneeded imports

## 0.9.0 (2024-04-22)

### Feat

- manage a shared state in the application

### Refactor

- use slot/signal instead of redis
- fix typos
- convert to use redis

## 0.8.3 (2024-04-12)

### Fix

- Change bad Qtimers

## v0.8.2 (2024-04-07)

### Fix

- Changed a bunch of stuff

## v0.8.1 (2024-04-07)

### Fix

- take out unnecessary checks
- add mark as completed

### Refactor

- use QTimer

## v0.8.0 (2024-02-22)

### Feature

* feat: change re-read logic and change variable names ([`aaa5297`](https://github.com/xevg/backblaze_status/commit/aaa5297363d413738bbf1f5dcebe9ea7b2786943))

* feat: add chunk information ([`7b1c7ea`](https://github.com/xevg/backblaze_status/commit/7b1c7ea2e4a51bb45140b660b11d30896a007d9c))

* feat: add chunk information ([`5f57204`](https://github.com/xevg/backblaze_status/commit/5f57204a10c0c501742f0d805872db93cca73c9f))

* feat: at chunk columns ([`04533d6`](https://github.com/xevg/backblaze_status/commit/04533d643b20e48221100f86560e13672a4ecb38))

### Fix

* fix: change divisor to 1024 ([`b8be445`](https://github.com/xevg/backblaze_status/commit/b8be445ba8ebacb3e0dc603399fee50c9293b12d))

* fix: remove incorrect dedup calculation ([`3846f71`](https://github.com/xevg/backblaze_status/commit/3846f71bbc13e694880915bd508183941905679b))

* fix: add emit ([`0eecfd1`](https://github.com/xevg/backblaze_status/commit/0eecfd1345f714fdd1c8c9f5f9d56e8fa1d23000))

* fix: minor changes ([`1444f5f`](https://github.com/xevg/backblaze_status/commit/1444f5f46fa438fa6acc416cfd9538904da7ca2c))

### Refactor

* refactor: change name of thread ([`c8c9ac5`](https://github.com/xevg/backblaze_status/commit/c8c9ac5b457b83d57d50d958f2abde6359b7d70d))

* refactor: change name of thread ([`68bd786`](https://github.com/xevg/backblaze_status/commit/68bd786eac61b2ae56f829ab22a3fa425ee855cc))

* refactor: change dialog table to model based ([`3c618ac`](https://github.com/xevg/backblaze_status/commit/3c618ac31233428eab3919f9ee329d949e4dd3e5))

* refactor: rename variables ([`d96c592`](https://github.com/xevg/backblaze_status/commit/d96c592436586fd7f6e0b18c5e3fb2fc12a62828))

* refactor: add ic and rename variables ([`e058def`](https://github.com/xevg/backblaze_status/commit/e058defeed835c8bfb88102e4e3edeeb0af00f09))

* refactor: take out whitespace ([`32bba05`](https://github.com/xevg/backblaze_status/commit/32bba0570d393cd02b8b9dc2b16a7eaea134fcc1))

* refactor: change variable names ([`39aef6c`](https://github.com/xevg/backblaze_status/commit/39aef6ccce163d3df8eadf70b47fb1685887ae43))

* refactor: change variable names ([`d2770c1`](https://github.com/xevg/backblaze_status/commit/d2770c15b02e6303417041f2e7c619be7de6d80f))


## v0.7.0 (2024-02-17)

### Feature

* feat: trying new version with extra sauce ([`8d4e776`](https://github.com/xevg/backblaze_status/commit/8d4e7766705ac75ad5009be5583e48de43aea68f))


## v0.6.0 (2024-02-17)

### Feature

* feat: trying new version with extra sauce ([`d9edb06`](https://github.com/xevg/backblaze_status/commit/d9edb065f31aebb5fbbe88a8192ccd2173c7524e))


## v0.5.0 (2024-02-17)

### Feature

* feat: trying new version ([`e9b0144`](https://github.com/xevg/backblaze_status/commit/e9b014489cfd724654250749406332c65bfc9d5d))


## v0.4.0 (2024-02-17)

### Feature

* feat: another silly change ([`eede703`](https://github.com/xevg/backblaze_status/commit/eede703f2d0225e7ed420d8f73d0f4e1d3b0d4ff))

* feat: try again ([`366adeb`](https://github.com/xevg/backblaze_status/commit/366adeb47d0c30f424d59b7d0a5b171574c8afc0))


## v0.3.1 (2024-02-17)

### Fix

* fix: update semantic-release ([`624b121`](https://github.com/xevg/backblaze_status/commit/624b1218cf1edff14c6582df835f55674600f41b))

* fix: silly change ([`1e48cbd`](https://github.com/xevg/backblaze_status/commit/1e48cbda09b93b122244518ce9a9c51938f475e0))


## v0.3.0 (2024-02-17)

### Feature

* feat: add backup_state_change ([`529c2f6`](https://github.com/xevg/backblaze_status/commit/529c2f67f916f1afd21399c59d09651bb32ca6d5))

* feat: add index ([`a1be053`](https://github.com/xevg/backblaze_status/commit/a1be0535d664f650e413b32ac8e1f47ae9eea478))

* feat: fix version number ([`50739a0`](https://github.com/xevg/backblaze_status/commit/50739a09c6d1b3a99e9195a1e679a70bd0880b45))

### Fix

* fix: change completed size ([`ffedcd1`](https://github.com/xevg/backblaze_status/commit/ffedcd15111e3c5e2b56e97457ae3af5a1187182))


## v0.2.0 (2024-02-17)

### Feature

* feat: fix version number ([`178699a`](https://github.com/xevg/backblaze_status/commit/178699acd40d565c766a993dd276154d58d11c0f))


## v0.1.4 (2024-02-17)

### Fix

* fix: fix size ([`bf0aeb2`](https://github.com/xevg/backblaze_status/commit/bf0aeb226256ef3feb6457b912d5399e66b3e394))

* fix: remove publishing ([`ac2bf0e`](https://github.com/xevg/backblaze_status/commit/ac2bf0e0b58d900b173661080a9122f5de25a052))

* fix: add sphinx ([`de0f486`](https://github.com/xevg/backblaze_status/commit/de0f4868abfdd4303e9c7aa2acb510f9ab10bd4d))


## v0.1.3 (2024-02-17)

### Fix

* fix: add sphinx ([`b4298f2`](https://github.com/xevg/backblaze_status/commit/b4298f2c02c800eb51a493d1d2adf09f52f35fe9))


## v0.1.2 (2024-02-17)

### Fix

* fix: add sphinx ([`e54a314`](https://github.com/xevg/backblaze_status/commit/e54a31468948b6ae0c2ac2f4424d2f8471bd157d))

* fix: remove testing for now ([`15654ab`](https://github.com/xevg/backblaze_status/commit/15654ab62278095ea8bca8efe9928437b761e836))

* fix: add test ([`a76abc2`](https://github.com/xevg/backblaze_status/commit/a76abc2c01b983dd9b38a26a0047a2a3cc195900))

* fix: add test ([`39b58a9`](https://github.com/xevg/backblaze_status/commit/39b58a9ed9f48d18ab68b5abeb424cb0efde71c1))

* fix: get rid og test ([`f537e32`](https://github.com/xevg/backblaze_status/commit/f537e326339af84380bde4afc4c296eb7553c90e))

* fix: added pytest ([`1bf5a12`](https://github.com/xevg/backblaze_status/commit/1bf5a127694d0484a2555baa39f0f0aae1216e80))


## v0.1.1 (2024-02-17)

### Fix

* fix: silly change ([`bc7fa95`](https://github.com/xevg/backblaze_status/commit/bc7fa95d28caf8adf84e3ffe8ef5691cb41fd008))


## v0.1.0 (2024-02-17)

### Feature

* feat: change to multiple lists ([`185bb2f`](https://github.com/xevg/backblaze_status/commit/185bb2fc66bd6303353c4df1cc321ad0adca9821))

* feat: add signals for files_updated and backup_running ([`24ef5ac`](https://github.com/xevg/backblaze_status/commit/24ef5ac383d01298132b7eb116f1cf033a3d92ba))

* feat: make generic BackupFileList ([`aadbc52`](https://github.com/xevg/backblaze_status/commit/aadbc52640eab871cddeb6f2eb65c882ad247d6d))

* feat: made is standard ([`a328066`](https://github.com/xevg/backblaze_status/commit/a3280660358b15c6e6c4f292474ec5d7a63702da))

* feat: add color information ([`0b82941`](https://github.com/xevg/backblaze_status/commit/0b82941705945d84d818b6fd78dcb8fb6b304fed))

* feat: added functionality

Great comment, isn&#39;t it? ([`335b6ae`](https://github.com/xevg/backblaze_status/commit/335b6ae290d087c82686e9012f30d4b44879a0c3))

* feat: fixed up ([`dc1b913`](https://github.com/xevg/backblaze_status/commit/dc1b91351b40d96bfafb52730aa7a796293172cc))

* feat: added first_pass logic ([`053bfef`](https://github.com/xevg/backblaze_status/commit/053bfef4cc6c5833efdbbef57cd98d352679e892))

* feat: added a bunch of stuff ([`ac805f6`](https://github.com/xevg/backblaze_status/commit/ac805f6203ebbb64706d16531f294a5791e3e575))

* feat: added lock file logging ([`0646512`](https://github.com/xevg/backblaze_status/commit/064651281974644e96a2b1e0c5bf612df0a4764c))

* feat: generic log class ([`e497d16`](https://github.com/xevg/backblaze_status/commit/e497d169fc869f0f34f0e89af5abaa5036600f0a))

* feat: parse lastfiletransmitted log ([`10c904a`](https://github.com/xevg/backblaze_status/commit/10c904a28e804d133d2b9be8c0bd0d1816a61ab6))

* feat: added class for batching ([`9917200`](https://github.com/xevg/backblaze_status/commit/99172004cc05f45033652a58fdb092c8f6e9c4b8))

* feat: added class for model view ([`24f1ac8`](https://github.com/xevg/backblaze_status/commit/24f1ac8195fbe9cfb9f17dedbe22fbf170ad04fb))

* feat: added more info fields ([`8c28bd0`](https://github.com/xevg/backblaze_status/commit/8c28bd08ab90e55dfa6b727c5cfc0825f8d962d9))

* feat: added icon ([`0c8d6f8`](https://github.com/xevg/backblaze_status/commit/0c8d6f86f232d08e62faf9f2a0853d5db06685be))

### Fix

* fix: fix value out of range, move window title ([`128a427`](https://github.com/xevg/backblaze_status/commit/128a427b7ef86d3d2419b311ff650bb0953952ad))

* fix: move to_do import ([`c949948`](https://github.com/xevg/backblaze_status/commit/c94994802ed392b16fce21f3e31393a2f4e1edb6))

* fix: various changes ([`dccadc9`](https://github.com/xevg/backblaze_status/commit/dccadc95d061e855efc7dad6890ab54088380ca3))

* fix: moved todo import ([`1eab178`](https://github.com/xevg/backblaze_status/commit/1eab1783ce9a83039247c22109941c82543cb0bf))

* fix: took out debug line ([`5ebfbf8`](https://github.com/xevg/backblaze_status/commit/5ebfbf8ad86c214257d7b1680ea846024e8ba0d3))

* fix: set current file ([`bbcb751`](https://github.com/xevg/backblaze_status/commit/bbcb751e70c99526e2701f72f94137d335b86c36))

* fix: fixed percentage calculation ([`73a221e`](https://github.com/xevg/backblaze_status/commit/73a221e1756ee7a9e8103bc46a6243ae6da5375f))

* fix: moved default_chunk_size to configuration ([`1761024`](https://github.com/xevg/backblaze_status/commit/1761024cee867c3b3ee76efd46ebb7eea76bbfd8))

* fix: start of dialog for todo files ([`5b8e6f2`](https://github.com/xevg/backblaze_status/commit/5b8e6f2daf3ac7a71bc39905524570cd0eba9650))

* fix: fixed the dialog and started adding menu items ([`ba7568a`](https://github.com/xevg/backblaze_status/commit/ba7568ac037b49fd03ab607b19e4f25ac73db8b8))

* fix: fixed the dialog and started adding menu items ([`378426e`](https://github.com/xevg/backblaze_status/commit/378426e16c9cfbee64050d8b63a2857c5ca61939))

* fix: not using this file anymore ([`c2326a4`](https://github.com/xevg/backblaze_status/commit/c2326a414348564b216917e8c50ac30a56f853aa))

* fix: added default_chunk_size ([`14566d4`](https://github.com/xevg/backblaze_status/commit/14566d45b342bc6d3e1117a14041950dc6987b84))

* fix: fixed a timestamp error introduced by a backblaze change ([`e3be88b`](https://github.com/xevg/backblaze_status/commit/e3be88bba1e162619ba9300e056daee80a256409))

* fix: added a first pass so it doesn&#39;t clog the GUI ([`bafd2e9`](https://github.com/xevg/backblaze_status/commit/bafd2e9477830f89f35b69d74e78062263a18686))

* fix: fixed how dedup size is saved ([`bfa2bc6`](https://github.com/xevg/backblaze_status/commit/bfa2bc6ff70ae738f008c959ec7ff9a49c758625))

* fix: checked for zero list size ([`2bdb231`](https://github.com/xevg/backblaze_status/commit/2bdb2318144a61c3d53ab7c0c534a223280f99d5))

* fix: took out darkmodetheme ([`5d71cbc`](https://github.com/xevg/backblaze_status/commit/5d71cbcfff4d194453996422a2441853fdaba461))

* fix: added more dependencies ([`37deb92`](https://github.com/xevg/backblaze_status/commit/37deb9206f3b486d15fa3c2c2bd28d0c762bd79b))

* fix: added reference to icons ([`cbd1d3a`](https://github.com/xevg/backblaze_status/commit/cbd1d3aa6d54f2134ec86d697bdd710de9dd7f1f))

* fix: removed a cr/lf ([`fb033a3`](https://github.com/xevg/backblaze_status/commit/fb033a365d0c50899452610889571c080e2e87f8))

* fix: removed movefile remnants ([`9545126`](https://github.com/xevg/backblaze_status/commit/95451264a519a02ae005e7022fc2bf69c9c7a2fe))

* fix: changed progresbar ([`dd10ad6`](https://github.com/xevg/backblaze_status/commit/dd10ad6941064c92b8119ebc825ac7fda57d62eb))

* fix: changed debugging ([`f64cae1`](https://github.com/xevg/backblaze_status/commit/f64cae17fc9f5730ac1b12f4961514713fd5bf54))

* fix: removed movefiles stuff ([`ec29a85`](https://github.com/xevg/backblaze_status/commit/ec29a8508aceffd0e87a343ebcaa8bf0b5433b79))

* fix: removed ([`78a67af`](https://github.com/xevg/backblaze_status/commit/78a67af202f1bd2b0bb8e65b0a9ff07d12f8f59c))

* fix: a little better, but needs more ([`0245d80`](https://github.com/xevg/backblaze_status/commit/0245d80f0eac642d874ede7265a014116c7b557a))

### Refactor

* refactor: poetry changes ([`452da6e`](https://github.com/xevg/backblaze_status/commit/452da6e2861bd0be02acc7ff502c4f845ddc3e4d))

* refactor: use different lists ([`9c7cb43`](https://github.com/xevg/backblaze_status/commit/9c7cb4387dd24a3724bc5bd9b1d00dfee47af268))

* refactor: make list_index optional

prepping for removing it completely ([`5f97f51`](https://github.com/xevg/backblaze_status/commit/5f97f51a980b8f61539479457e683cd5672e7fc3))

* refactor: renamed variables ([`52eb2a9`](https://github.com/xevg/backblaze_status/commit/52eb2a968e71363200c08ba0085602ae89018ebc))

* refactor: docs and cleanup ([`a5dad6e`](https://github.com/xevg/backblaze_status/commit/a5dad6ef5f6cc394dfb0067385c49924b14b3788))

* refactor: change variable names ([`b200d8d`](https://github.com/xevg/backblaze_status/commit/b200d8dcf5f419cc2ce13a082520d9cab06a195e))

* refactor: move some classes around ([`1db9415`](https://github.com/xevg/backblaze_status/commit/1db9415606549b7d2244111dd5e449bc8a3c8179))

* refactor: moved classes out ([`0b61b3e`](https://github.com/xevg/backblaze_status/commit/0b61b3e6b06b11153b38a51f1558c8af05e71fcf))

* refactor: tons of changes ([`6bdb58b`](https://github.com/xevg/backblaze_status/commit/6bdb58b029243f3dc6131c2f98a2b8f8df63acae))

* refactor: tons of changes ([`53f0a87`](https://github.com/xevg/backblaze_status/commit/53f0a87c4fa0fb47f1b80f6ad0e73c308f717324))

* refactor: moved progress out ([`934fc42`](https://github.com/xevg/backblaze_status/commit/934fc429bf6aec5e1bf9e4c9be5c3dec6b104332))

* refactor: changed name ([`3acdb99`](https://github.com/xevg/backblaze_status/commit/3acdb992de88dfe4a03c54490034a9accbfbac9c))

* refactor: changed name ([`ad00f1a`](https://github.com/xevg/backblaze_status/commit/ad00f1ac718fbff369737146fd3dade1b17cf808))

* refactor: changed to QTableView ([`ca73865`](https://github.com/xevg/backblaze_status/commit/ca7386593ac0b7e30650bb0dc2dd506f56aae0d4))

### Unknown

* doc: add documentation ([`eb90b05`](https://github.com/xevg/backblaze_status/commit/eb90b055a706841477569a9a13fd20e1584e8ff3))

* Freeze after moving away from db modules ([`82aa04b`](https://github.com/xevg/backblaze_status/commit/82aa04b9de5f6f844ccf0f9e2e992d3f946d2332))

* moved ([`7d26b39`](https://github.com/xevg/backblaze_status/commit/7d26b39882d6e09051fad5bbabf77eea262d1c10))

* Before Changing How it transmits ([`20aa2fc`](https://github.com/xevg/backblaze_status/commit/20aa2fcdbf3c4cf96f5ff10aa29fa4dfa32f5447))

* Before Changing Threads ([`e957181`](https://github.com/xevg/backblaze_status/commit/e95718174ace6538c2280004501260751255de50))

* initial package setup ([`c263f6f`](https://github.com/xevg/backblaze_status/commit/c263f6fa32f44f6103d2e083eba7b3ba6d7f5bfb))
