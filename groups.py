import sys
from itertools import combinations
import json

from ortools.sat.python import cp_model
import numpy as np
from golferInfo import golferInfo

def main():
  games = ['Wolf', 'Small Scramble', 'Yellow Ball', 'Large Scramble', 'Individual']
  rounds = range(len(games))
  teams = range(4)
  carts = range(2)
  teamSizes = [3, 3, 3, 4]

  # Carts are double occupancy except:
  singleOccupancyCarts = [
    { 'team': 0, 'cart': 1 },
    { 'team': 1, 'cart': 1 },
    { 'team': 2, 'cart': 1 },
  ]

  golfers = [golfer['name'] for golfer in golferInfo]
  golferCombinations = list(combinations(golfers, 2))

  friendCombinations = {}
  for g1, g2 in combinations(golferInfo, 2):
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
  for golfer1, golfer2 in golferCombinations:
    for round in rounds:
      for team in teams:
        for cart in carts:
          ridingTogether[(golfer1, golfer2, round, team, cart)] = model.NewBoolVar(f'g{golfer1}+g{golfer2}r{round}t{team}c{cart}')

          # Link "ridingTogether" to "cartAssignments":
          # https://github.com/google/or-tools/blob/master/ortools/sat/doc/boolean_logic.md#product-of-two-boolean-variables
          x = cartAssignments[(golfer1, round, team, cart)]
          y = cartAssignments[(golfer2, round, team, cart)]
          p = ridingTogether[(golfer1, golfer2, round, team, cart)]
          model.AddBoolOr([x.Not(), y.Not(), p])
          model.AddImplication(p, x)
          model.AddImplication(p, y)

  # Variables to indicate whether golfer is riding alone
  # (golfer, round) => [0...1]
  ridingAlone = {}
  for golfer in golfers:
    for round in rounds:
      a = model.NewBoolVar(f'alone+g{golfer}r{round}')
      ridingAlone[(golfer, round)] = a
      # Link "ridingAlone" to "cartAssignments"
      for singleOccupancyCart in singleOccupancyCarts:
        team = singleOccupancyCart['team']
        cart = singleOccupancyCart['cart']
        model.AddImplication(cartAssignments[(golfer, round, team, cart)], a)

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

        # Link "teamedTogether" to "teamAssignments":
        # https://github.com/google/or-tools/blob/master/ortools/sat/doc/boolean_logic.md#product-of-two-boolean-variables
        x = teamAssignments[(golfer1, round, team)]
        y = teamAssignments[(golfer2, round, team)]
        p = teamedTogether[(golfer1, golfer2, round, team)]
        model.AddBoolOr([x.Not(), y.Not(), p])
        model.AddImplication(p, x)
        model.AddImplication(p, y)

  # Define team sizes:
  def setTeamSize(team, size):
    for round in rounds:
      model.Add(
        sum(
          teamAssignments[(golfer, round, team)] for golfer in golfers
        ) == size
      )

  for team, size in enumerate(teamSizes):
    setTeamSize(team, size)

  # Define how many riders are in each cart:
  def setCartOccupancy(team, cart, occupancy):
    for round in rounds:
      model.Add(
        sum(
          cartAssignments[(golfer, round, team, cart)] for golfer in golfers
        ) == occupancy
      )

  for team in teams:
    for cart in carts:
      occupancy = (
        1 if { 'team': team, 'cart': cart } in singleOccupancyCarts
        else 2
      )
      setCartOccupancy(team, cart, occupancy)

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
        ('Reid' in [golfer1, golfer2] and 'Kent' in [golfer1, golfer2]) or
        ('Reid' in [golfer1, golfer2] and 'Dan' in [golfer1, golfer2]) or
        ('Bob' in [golfer1, golfer2] and 'Jon H' in [golfer1, golfer2]) or
        ('Bob' in [golfer1, golfer2] and 'Dan' in [golfer1, golfer2]) or
        ('Jon H' in [golfer1, golfer2] and 'Dan' in [golfer1, golfer2]) or
        ('Jay' in [golfer1, golfer2] and 'Erik' in [golfer1, golfer2]) or
        ('Jay' in [golfer1, golfer2] and 'Jeff' in [golfer1, golfer2]) or
        ('Erik' in [golfer1, golfer2] and 'Jeff' in [golfer1, golfer2]) or
        ('Jon D' in [golfer1, golfer2] and 'James' in [golfer1, golfer2]) or
        ('Dan' in [golfer1, golfer2] and 'Brady' in [golfer1, golfer2])
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

  # Ride alone between 1 and 2 times:
  for golfer in golfers:
    model.Add(
      sum(ridingAlone[(golfer, round)]
          for round in rounds
          ) >= 1
    )
    model.Add(
      sum(ridingAlone[(golfer, round)]
          for round in rounds
      ) <= 2
    )

  # Don't team with someone too much:
  for golfer1, golfer2 in golferCombinations:
    model.Add(
      sum(teamedTogether[(golfer1, golfer2, round, team)]
        for round in rounds
        for team in teams
      ) <= 2
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

  # Capture groupings in a dictionary for JSON output:
  groupings = { 'rounds': [] }
  for round in rounds:
    groupings['rounds'].append({ 'teams': [] })
    for team in teams:
      groupings['rounds'][round]['teams'].append({ 'carts': [] })
      for cart in carts:
        groupings['rounds'][round]['teams'][team]['carts'].append([])
        riders = []
        for golfer in golfers:
          if solver.Value(cartAssignments[(golfer, round, team, cart)]) == 1:
            riders.append(golfer)
            groupings['rounds'][round]['teams'][team]['carts'][cart].append(golfer)

  # Print groupings:
  print()
  for roundNum, round in enumerate(groupings['rounds']):
    print(f'Round {roundNum + 1} ({games[roundNum]}):')
    for teamNum, team in enumerate(round['teams']):
      print(f'  Team {teamNum + 1}:')
      for cartNum, riders in enumerate(team['carts']):
        print('    ', ' + '.join(riders))

  # Print player-by-player teaming and riding statistics:
  print()
  for golfer1 in golfers:
    print()
    print(f'{golfer1}:')

    for golfer2 in [g for g in golfers if g != golfer1]:
      # We'll print repeated elements (`Dan + Kent` as well as `Kent +
      # Dan`), but model variables aren't repeated. So find whether we
      # need to index in the opposite order:
      invertOrder = (golfer1, golfer2) not in golferCombinations
      key = (
        (golfer1, golfer2) if not invertOrder
        else (golfer2, golfer1)
      )
      numRiding = sum(
        solver.Value(ridingTogether[(*key, round, team, cart)])
          for round in rounds
          for team in teams
          for cart in carts
      )
      numTeamed = sum(
        solver.Value(teamedTogether[(*key, round, team)])
          for round in rounds
          for team in teams
      )
      print(f'\t{golfer2}\triding: {numRiding}, teamed: {numTeamed}')

  # Write groupings to JSON file:
  with open('groupings.json', 'w') as outfile:
    json.dump(groupings, outfile, indent=2)

if __name__ == '__main__':
  main()
