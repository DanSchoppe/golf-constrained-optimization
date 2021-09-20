import sys
from itertools import combinations

from ortools.sat.python import cp_model
import numpy as np
from golferInfo import golferInfo

def main():
  rounds = range(5)
  teams = range(3)
  carts = range(2)

  golfers = [golfer['name'] for golfer in golferInfo]
  golferCombinations = list(combinations(golfers, 2))

  restrictedCombinations = {}
  friendCombinations = {}
  for g1, g2 in combinations(golferInfo, 2):
    restricted = (
      (not g1['vaxed'] and g2['concerned']) or
      (g1['concerned'] and not g2['vaxed'])
    )
    restrictedCombinations[(g1['name'], g2['name'])] = restricted

    friends = (
      g1['name'] in g2['friends'] or
      g2['name'] in g1['friends']
    )
    friendCombinations[(g1['name'], g2['name'])] = friends

  model = cp_model.CpModel()

  # Cart assignments:
  # (golfer, round, team, cart) => [0...1]
  cartAssignments = {}
  for golfer in golfers:
    for round in rounds:
      for team in teams:
        for cart in carts:
          cartAssignments[(golfer, round, team, cart)] = model.NewBoolVar(f'g{golfer}r{round}t{team}c{cart}')

  # Variables to indicate whether golfers are riding together
  # (golfer1, golfer2, round, team, cart) => [0...1]
  ridingTogether = {}
  for round in rounds:
    for team in teams:
      for cart in carts:
        for golfer1, golfer2 in golferCombinations:
          ridingTogether[(golfer1, golfer2, round, team, cart)] = model.NewBoolVar(f'g{golfer1}+g{golfer2}r{round}t{team}c{cart}')

          # Link "ridingTogether" to "cartAssignments":
          # https://github.com/google/or-tools/blob/master/ortools/sat/doc/boolean_logic.md#product-of-two-boolean-variables
          x = cartAssignments[(golfer1, round, team, cart)]
          y = cartAssignments[(golfer2, round, team, cart)]
          p = ridingTogether[(golfer1, golfer2, round, team, cart)]
          model.AddBoolOr([x.Not(), y.Not(), p])
          model.AddImplication(p, x)
          model.AddImplication(p, y)

  # Variables to indicate which team golfers are on for a given round
  # (golfer, round, team) => [0...1]
  teamAssignments = {}
  for golfer in golfers:
    for round in rounds:
      for team in teams:
        t = model.NewBoolVar(f'g{golfer}r{round}t{team}')
        teamAssignments[(golfer, round, team)] = t
        for cart in carts:
          model.AddImplication(cartAssignments[(golfer, round, team, cart)], t)

  # Variables to indicate whether golfers are teamed together
  # (golfer1, golfer2, round, team) => [0...1]
  teamedTogether = {}
  for round in rounds:
    for team in teams:
      for golfer1, golfer2 in golferCombinations:
        teamedTogether[(golfer1, golfer2, round, team)] = model.NewBoolVar(f'g{golfer1}+g{golfer2}r{round}t{team}')

        # Link "teamedTogether" to "cartAssignments":
        # https://github.com/google/or-tools/blob/master/ortools/sat/doc/boolean_logic.md#product-of-two-boolean-variables
        x = teamAssignments[(golfer1, round, team)]
        y = teamAssignments[(golfer2, round, team)]
        p = teamedTogether[(golfer1, golfer2, round, team)]
        model.AddBoolOr([x.Not(), y.Not(), p])
        model.AddImplication(p, x)
        model.AddImplication(p, y)

  # All but last cart contains two golfers
  for round in rounds:
    for team in teams[0:-1]:
      for cart in carts:
        model.Add(
          sum(
            cartAssignments[(golfer, round, team, cart)] for golfer in golfers
          ) == 2
        )
  for round in rounds:
    for team in teams[-1:]:
      for cart in carts[0:-1]:
        model.Add(
          sum(
            cartAssignments[(golfer, round, team, cart)] for golfer in golfers
          ) == 2
        )
      for cart in carts[-1:]:
        model.Add(
          sum(
            cartAssignments[(golfer, round, team, cart)] for golfer in golfers
          ) == 1
        )

  # All but last team contains four golfers
  for round in rounds:
    for team in teams[0:-1]:
      model.Add(
        sum(
          teamAssignments[(golfer, round, team)] for golfer in golfers
        ) == 4
      )
    for team in teams[-1:]:
      model.Add(
        sum(
          teamAssignments[(golfer, round, team)] for golfer in golfers
        ) == 3
      )

  # Each golfer is in exactly one cart per round
  for golfer in golfers:
    for round in rounds:
      model.Add(
        sum(
          cartAssignments[(golfer, round, team, cart)] for team in teams for cart in carts
        ) == 1
      )

  # Ride with others <=1, with some hard constraints:
  for golfer1, golfer2 in golferCombinations:
    if (
        ('Kent' in [golfer1, golfer2] and 'Reid' in [golfer1, golfer2]) or
        ('Dan' in [golfer1, golfer2] and 'Reid' in [golfer1, golfer2]) or
        ('Erik' in [golfer1, golfer2] and 'Jeff' in [golfer1, golfer2]) or
        ('Erik' in [golfer1, golfer2] and 'Jay' in [golfer1, golfer2]) or
        ('Jeff' in [golfer1, golfer2] and 'Jay' in [golfer1, golfer2])
    ):
      model.Add(
        sum(ridingTogether[(golfer1, golfer2, round, team, cart)]
          for round in rounds
          for team in teams
          for cart in carts
        ) == 1
      )
    else:
      model.Add(
        sum(ridingTogether[(golfer1, golfer2, round, team, cart)]
          for round in rounds
          for team in teams
          for cart in carts
        ) <= 1
      )

  # Never team with someone four times
  for golfer1, golfer2 in golferCombinations:
    model.Add(
      sum(teamedTogether[(golfer1, golfer2, round, team)]
        for round in rounds
        for team in teams
      ) <= 3
    )

  # COVID preference constraint
  for golfer1, golfer2 in golferCombinations:
    if restrictedCombinations[(golfer1, golfer2)]:
      model.Add(
        sum(ridingTogether[(golfer1, golfer2, round, team, cart)]
          for round in rounds
          for team in teams
          for cart in carts
        ) == 0
      )

  # Friendship preference
  model.Maximize(
    # sum(
    #   friendCombinations[(golfer1, golfer2)] * ridingTogether[(golfer1, golfer2, round, team, cart)]
    #   for golfer1, golfer2 in golferCombinations
    #   for round in rounds
    #   for team in teams
    #   for cart in carts
    # )
    sum(
      friendCombinations[(golfer1, golfer2)] * teamedTogether[(golfer1, golfer2, round, team)]
      for golfer1, golfer2 in golferCombinations
      for round in rounds
      for team in teams
    )
  )

  print(model.ModelStats())

  solver = cp_model.CpSolver()
  solver.parameters.num_search_workers = 8
  # solver.parameters.max_time_in_seconds = 100
  solver.Solve(model, cp_model.ObjectiveSolutionPrinter())

  # Results:
  results = np.zeros([len(rounds), len(teams), len(carts), 2], dtype="S10")
  for round in rounds:
    print('Round', round)
    for team in teams:
      print('  Team', team)
      for cart in carts:
        riders = []
        for golfer in golfers:
          if solver.Value(cartAssignments[(golfer, round, team, cart)]) == 1:
            riders.append(golfer)
        print('    ', ' + '.join(riders))
        for i, rider in enumerate(riders):
          results[round, team, cart, i] = rider

  # Times teaming and riding together:
  for golfer1, golfer2 in golferCombinations:
    print(
      f'{golfer1} + {golfer2}\t',
      'riding:',
      sum(
        solver.Value(ridingTogether[(golfer1, golfer2, round, team, cart)])
        for round in rounds
        for team in teams
        for cart in carts
      ),
      ', teamed:',
      sum(
        solver.Value(teamedTogether[(golfer1, golfer2, round, team)])
        for round in rounds
        for team in teams
      )
    )

  np.savetxt(
    sys.stdout.buffer,
    results.astype(np.str_).flatten().reshape([5,12]).transpose(),
    fmt='%s',
    delimiter='\t'
  )


if __name__ == '__main__':
  main()
