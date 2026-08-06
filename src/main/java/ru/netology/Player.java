package ru.netology;

import java.util.Objects;

public class Player {

    private final int id;
    private final String name;
    private final int strength;

    public Player(int id, String name, int strength) {
        this.id = id;
        this.name = name;
        this.strength = strength;
    }

    public int getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public int getStrength() {
        return strength;
    }

    @Override
    public boolean equals(Object object) {
        if (this == object) {
            return true;
        }
        if (object == null || getClass() != object.getClass()) {
            return false;
        }
        Player player = (Player) object;
        return id == player.id && strength == player.strength && name.equals(player.name);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, name, strength);
    }
}
