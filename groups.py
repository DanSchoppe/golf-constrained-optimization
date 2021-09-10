from itertools import combinations

from ortools.sat.python import cp_model

def main():

  numRounds = 5
  numTeams = 3
  numCarts = 2

  golfers = [
    'Kent', 'Brandon', 'Erik', 'Jay', 'Joe', 'Dan',
    'Jeff', 'Brady', 'Reid', 'James', 'Brian', 'Kyle'
  ]
  rounds = range(numRounds)
  teams = range(numTeams)
  carts = range(numCarts)

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
        for golfer1, golfer2 in combinations(golfers, 2):
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
      for golfer1, golfer2 in combinations(golfers, 2):
        teamedTogether[(golfer1, golfer2, round, team)] = model.NewBoolVar(f'g{golfer1}+g{golfer2}r{round}t{team}')

        # Link "teamedTogether" to "cartAssignments":
        # https://github.com/google/or-tools/blob/master/ortools/sat/doc/boolean_logic.md#product-of-two-boolean-variables
        x = teamAssignments[(golfer1, round, team)]
        y = teamAssignments[(golfer2, round, team)]
        p = teamedTogether[(golfer1, golfer2, round, team)]
        model.AddBoolOr([x.Not(), y.Not(), p])
        model.AddImplication(p, x)
        model.AddImplication(p, y)

  # Each cart contains two golfers
  for round in rounds:
    for team in teams:
      for cart in carts:
        model.Add(
          sum(
            cartAssignments[(golfer, round, team, cart)] for golfer in golfers
          ) == 2
        )

  # Each golfer is in exactly one cart per round
  for golfer in golfers:
    for round in rounds:
      model.Add(
        sum(
          cartAssignments[(golfer, round, team, cart)] for team in teams for cart in carts
        ) == 1
      )

  # Never ride with someone twice
  for golfer1, golfer2 in combinations(golfers, 2):
    model.Add(
      sum(ridingTogether[(golfer1, golfer2, round, team, cart)]
       for round in rounds
       for team in teams
       for cart in carts
      ) <= 1
    )

  # TODO: COVID preference constraint

  # TODO: Friendship preference

  solver = cp_model.CpSolver()
  solver.Solve(model)

  # Results:
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

  # Times teaming and riding together:
  for golfer1, golfer2 in combinations(golfers, 2):
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

if __name__ == '__main__':
  main()
