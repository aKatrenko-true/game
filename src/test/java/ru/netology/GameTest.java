package ru.netology;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class GameTest {

    @Test
    public void shouldRegisterPlayersAndDeclareFirstPlayerWinner() {
        Game game = new Game();
        game.register(new Player(1, "Анна", 30));
        game.register(new Player(2, "Борис", 20));

        int actual = game.round("Анна", "Борис");

        assertEquals(1, actual);
    }

    @Test
    public void shouldDeclareSecondPlayerWinner() {
        Game game = new Game();
        game.register(new Player(1, "Анна", 20));
        game.register(new Player(2, "Борис", 30));

        int actual = game.round("Анна", "Борис");

        assertEquals(2, actual);
    }

    @Test
    public void shouldDeclareDraw() {
        Game game = new Game();
        game.register(new Player(1, "Анна", 25));
        game.register(new Player(2, "Борис", 25));

        int actual = game.round("Анна", "Борис");

        assertEquals(0, actual);
    }

    @Test
    public void shouldThrowWhenFirstPlayerIsNotRegistered() {
        Game game = new Game();
        game.register(new Player(1, "Анна", 25));

        assertThrows(NotRegisteredException.class, () -> game.round("Борис", "Анна"));
    }

    @Test
    public void shouldThrowWhenSecondPlayerIsNotRegistered() {
        Game game = new Game();
        game.register(new Player(1, "Анна", 25));

        assertThrows(NotRegisteredException.class, () -> game.round("Анна", "Борис"));
    }
}
