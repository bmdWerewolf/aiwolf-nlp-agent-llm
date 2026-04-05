import random

def simulate_game():
    # 角色定义
    roles = {
        'wolf1': 'wolf', 'wolf2': 'wolf',
        'madman': 'human', # 狂人算人头，但属于狼阵营
        'seer': 'human', 'medium': 'human', 'hunter': 'human',
        'v1': 'human', 'v2': 'human', 'v3': 'human'
    }
    
    alive = list(roles.keys())
    wolves = {p for p, r in roles.items() if r == 'wolf'}
    
    # 占卜师的情报库: {player: is_wolf}
    seer_knowledge = {} 
    
    def check_win(current_alive):
        current_wolves = [p for p in current_alive if p in wolves]
        # 1. 村人胜利：狼全灭
        if not current_wolves:
            return 'villagers'
        # 2. 狼人胜利：狼人数 >= 人类数 (狂人算人类)
        if len(current_wolves) * 2 >= len(current_alive):
            return 'wolves'
        return None

    # --- 第 0 晚 (初始信息) ---
    # 占卜师先验尸/验人 (假设第0晚随机验一个非自己的人)
    if 'seer' in alive:
        target = random.choice([p for p in alive if p != 'seer'])
        seer_knowledge[target] = (roles[target] == 'wolf')
    
    # 狼人首刀 (第0晚不判定胜负，假设不刀占卜师以保证游戏开展，或者完全随机)
    first_kill = random.choice([p for p in alive if p in wolves or roles[p] == 'human']) # 这里简化为不刀狼人自己
    if first_kill in alive: alive.remove(first_kill)

    days = 0
    while True:
        days += 1
        
        # --- 白天：智能投票 ---
        # 1. 如果占卜师活着且有“黑麦”（查杀），全场投狼
        # 2. 如果没有查杀，随机投，但避开占卜师已知的“金水”
        black_checks = [p for p, is_wolf in seer_knowledge.items() if is_wolf and p in alive]
        gold_checks = [p for p, is_wolf in seer_knowledge.items() if not is_wolf and p in alive]
        
        if 'seer' in alive and black_checks:
            vote_target = random.choice(black_checks)
        else:
            # 排除掉已知的好人进行随机投票
            potential_targets = [p for p in alive if p not in gold_checks]
            if not potential_targets: potential_targets = alive # 万一全是好人
            vote_target = random.choice(potential_targets)
        
        if vote_target in alive: alive.remove(vote_target)
        
        # 投票后判定
        winner = check_win(alive)
        if winner: return days, winner

        # --- 夜晚：角色行动 ---
        # 1. 占卜师行动
        if 'seer' in alive:
            unknowns = [p for p in alive if p not in seer_knowledge and p != 'seer']
            if unknowns:
                target = random.choice(unknowns)
                seer_knowledge[target] = (roles[target] == 'wolf')

        # 2. 狩人护卫 (简单策略：活着就优先守占卜师，否则守自己)
        protected = None
        if 'hunter' in alive:
            if 'seer' in alive:
                protected = 'seer'
            else:
                protected = 'hunter'
        
        # 3. 狼人杀人
        # 狼人会优先杀占卜师（如果知道谁是占卜师），这里简化为优先刀占卜师，否则随机
        if 'seer' in alive:
            kill_target = 'seer'
        else:
            kill_target = random.choice([p for p in alive if p not in wolves])
            
        # 平安夜判定
        if kill_target != protected:
            if kill_target in alive: alive.remove(kill_target)
        
        # 刀人后判定
        winner = check_win(alive)
        if winner: return days, winner

# --- 蒙特卡ロ实验 ---
simulations = 50000
results = {'villagers': 0, 'wolves': 0}
total_days = 0

for _ in range(simulations):
    d, w = simulate_game()
    results[w] += 1
    total_days += d

print(f"--- 模拟结果 ({simulations}局) ---")
print(f"平均游戏天数: {total_days / simulations:.2f}")
print(f"村人胜率: {results['villagers'] / simulations:.2%}")
print(f"人狼胜率: {results['wolves'] / simulations:.2%}")