package ru.netology;

import java.util.ArrayList;
import java.util.List;

public class Game {

    private final List<Player> players = new ArrayList<>();

    public void register(Player player) {
        players.add(player);
    }

    public int round(String playerName1, String playerName2) {
        Player firstPlayer = findByName(playerName1);
        if (firstPlayer == null) {
            throw new NotRegisteredException("Player " + playerName1 + " is not registered");
        }

        Player secondPlayer = findByName(playerName2);
        if (secondPlayer == null) {
            throw new NotRegisteredException("Player " + playerName2 + " is not registered");
        }

        if (firstPlayer.getStrength() > secondPlayer.getStrength()) {
            return 1;
        }
        if (firstPlayer.getStrength() < secondPlayer.getStrength()) {
            return 2;
        }
        return 0;
    }

    private Player findByName(String name) {
        for (Player player : players) {
            if (player.getName().equals(name)) {
                return player;
            }
        }
        return null;
    }
}
