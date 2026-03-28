CREATE TABLE voters (
    id INT IDENTITY(1,1) PRIMARY KEY,
    voter_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    qr_filename VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL
);
