import { useState } from "react";

interface LogoProps {
  className?: string;
  size?: number;
}

export default function Logo({ className = "", size = 36 }: LogoProps) {
  const [isLoaded, setIsLoaded] = useState(false);

  return (
    <img
      src="/logo.svg"
      alt="RS Recruiting"
      width={size}
      height={size}
      onLoad={() => setIsLoaded(true)}
      onError={() => setIsLoaded(true)}
      style={{ width: size, height: size, opacity: isLoaded ? 1 : 0, transition: "opacity 0.25s ease" }}
      className={`inline-block shrink-0 ${className}`}
    />
  );
}
