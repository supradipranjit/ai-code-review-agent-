public class Demo {

    // SQL Injection
    public String getUser(String username) {
        return "SELECT * FROM users WHERE name='" + username + "'";
    }

    // Hardcoded password
    public void connect() {
        String password = "admin123";
        System.out.println("Connecting with: " + password);
    }
}
