from gym.envs.registration import register

register(
    id="vssOri-v0",
    entry_point="envs.vss_strat:VSSStratEnv",
    kwargs={"stratified": False},
    max_episode_steps=1200,
)

register(
    id="vssStrat-v0",
    entry_point="envs.vss_strat:VSSStratEnv",
    max_episode_steps=1200,
)

register(
    id="LunarLanderStrat-v0",
    entry_point="envs.lunar_lander_strat:LunarLanderStrat",
    max_episode_steps=1000,
    reward_threshold=200,
)

register(
    id="LunarLanderOri-v0",
    entry_point="envs.lunar_lander_strat:LunarLanderStrat",
    kwargs={"stratified": False},
    max_episode_steps=1000,
    reward_threshold=200,
)

register(
    id="LunarLanderContinuousStrat-v0",
    entry_point="envs.lunar_lander_strat:LunarLanderContinuousStrat",
    max_episode_steps=1000,
    reward_threshold=200,
)

register(
    id="LunarLanderContinuousOri-v0",
    entry_point="envs.lunar_lander_strat:LunarLanderContinuousStrat",
    kwargs={"stratified": False},
    max_episode_steps=1000,
    reward_threshold=200,
)

register(
    id="HalfCheetahStrat-v0",
    entry_point="envs.half_cheetah_strat:HalfCheetahStratEnv",
    max_episode_steps=1000,
    reward_threshold=4800.0,
)

register(
    id="HalfCheetahOri-v0",
    entry_point="envs.half_cheetah_strat:HalfCheetahStratEnv",
    kwargs={"stratified": False},
    max_episode_steps=1000,
    reward_threshold=4800.0,
)

register(
    id="HumanoidStrat-v0",
    entry_point="envs.humanoid_strat:HumanoidStratEnv",
    max_episode_steps=1000,
)

register(
    id="HumanoidOri-v0",
    entry_point="envs.humanoid_strat:HumanoidStratEnv",
    kwargs={"stratified": False},
    max_episode_steps=1000,
)
