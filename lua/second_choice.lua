-- 单字双拼后补一个空形码分隔符（如 zl;）时，把当前第二候选提到首位。
-- 继续输入形码字母后恢复正常的形码筛选与排序。
local M = {}

local function make_candidate_reader(input)
    local iterator, state, control = input:iter()
    return function()
        local cand = iterator(state, control)
        control = cand
        return cand
    end
end

local function is_single_character(cand)
    return cand and cand.text and utf8.len(cand.text) == 1
end

function M.func(input, env)
    local current_input = env.engine.context.input or ""
    if not current_input:match("^[a-z][a-z];$") then
        for cand in input:iter() do yield(cand) end
        return
    end

    local next_candidate = make_candidate_reader(input)
    local first = next_candidate()
    if not first then return end

    local second = next_candidate()
    if second and is_single_character(first) and is_single_character(second) then
        yield(second)
        yield(first)
    else
        yield(first)
        if second then yield(second) end
    end

    while true do
        local cand = next_candidate()
        if not cand then break end
        yield(cand)
    end
end

return M
